import asyncio
import logging
import random
from typing import TypeVar

import openai
from openai.types.chat import ChatCompletion
from openai.types.shared_params import ResponseFormatJSONObject, ResponseFormatJSONSchema
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import BaseModel

from app.application.dto.ai import DeepAnalysisData, FastTrackResultData
from app.core.exceptions import AIResponseError
from app.domain.ports.ai_service import AIService
from app.infrastructure.ai import prompts

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3
BASE_DELAY = 2.0
FAST_TRACK_TIMEOUT = 30
DEEP_TIMEOUT = 60
MAX_CONCURRENT_REQUESTS = 2

# Status codes that should not be retried
_NON_RETRYABLE_4XX = {400, 401, 403, 404, 422}


class OpenAIService(AIService):
    """AIService implementation backed by the OpenAI-compatible Chat Completions API.

    Accepts any provider that speaks the OpenAI protocol (OpenAI, Azure OpenAI,
    local Ollama, OpenRouter, etc.) via ``base_url``.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._model = model
        self._client = openai.AsyncOpenAI(
            api_key=api_key or "sk-placeholder",
            base_url=base_url,
        )
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def analyze_fast_track(self, job_description: str, resume: str) -> FastTrackResultData:
        return await self._call_with_retry(
            prompt_type="fast_track",
            system_prompt=prompts.FAST_TRACK_SYSTEM_PROMPT,
            user_prompt=prompts.fast_track_user_prompt(job_description, resume),
            schema=FastTrackResultData,
            timeout=FAST_TRACK_TIMEOUT,
        )

    async def analyze_deep(self, job_description: str, resume: str) -> DeepAnalysisData:
        return await self._call_with_retry(
            prompt_type="deep",
            system_prompt=prompts.DEEP_SYSTEM_PROMPT,
            user_prompt=prompts.deep_user_prompt(job_description, resume),
            schema=DeepAnalysisData,
            timeout=DEEP_TIMEOUT,
        )

    async def _call_with_retry(
        self,
        prompt_type: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        timeout: int,
    ) -> T:
        last_exception: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                async with self._semaphore:
                    response = await asyncio.wait_for(
                        self._make_api_call(system_prompt, user_prompt, schema),
                        timeout=timeout,
                    )

                usage = response.usage
                if usage:
                    logger.info(
                        "OpenAI %s tokens: prompt=%s, completion=%s, total=%s",
                        prompt_type,
                        usage.prompt_tokens,
                        usage.completion_tokens,
                        usage.total_tokens,
                    )

                raw_content = response.choices[0].message.content
                if not raw_content:
                    raise AIResponseError(
                        "OpenAI returned empty content",
                        raw_response=raw_content,
                    )

                try:
                    parsed = schema.model_validate_json(raw_content)
                except Exception as parse_err:
                    raise AIResponseError(
                        f"OpenAI response could not be parsed as {schema.__name__}: {parse_err}",
                        raw_response=raw_content,
                    ) from parse_err

                return parsed

            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    "OpenAI %s attempt %d timed out after %ds",
                    prompt_type,
                    attempt + 1,
                    timeout,
                )
            except openai.APIStatusError as e:
                last_exception = e
                logger.warning(
                    "OpenAI %s attempt %d failed: %s (status=%s)",
                    prompt_type,
                    attempt + 1,
                    e.message,
                    e.status_code,
                )
                if e.status_code in _NON_RETRYABLE_4XX:
                    raise AIResponseError(
                        f"Non-retryable OpenAI error {e.status_code}: {e.message}",
                        raw_response=str(e),
                    ) from e
            except AIResponseError:
                raise

            if attempt < MAX_RETRIES - 1:
                delay = (BASE_DELAY * (2**attempt)) + random.uniform(0, 1)
                logger.info("Retrying OpenAI %s in %.2f seconds...", prompt_type, delay)
                await asyncio.sleep(delay)

        raise AIResponseError(
            f"OpenAI {prompt_type} failed after {MAX_RETRIES} attempts",
            raw_response=str(last_exception),
        )

    async def _make_api_call(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> ChatCompletion:
        """Call the Chat Completions endpoint with a JSON schema response_format.

        Uses ``json_schema`` response_format when the model supports it
        (OpenAI gpt-4o and later).  Falls back to ``json_object`` for older
        models or providers that don't support strict structured outputs.
        """
        json_schema_fmt = ResponseFormatJSONSchema(
            type="json_schema",
            json_schema=JSONSchema(
                name=schema.__name__,
                strict=True,
                schema=schema.model_json_schema(),
            ),
        )

        try:
            return await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=json_schema_fmt,
            )
        except openai.APIStatusError as e:
            # Some providers don't support json_schema response_format;
            # fall back to plain json_object mode and let the caller validate.
            if e.status_code == 400 and "response_format" in str(e).lower():
                logger.warning(
                    "json_schema response_format unsupported by provider, "
                    "falling back to json_object"
                )
                return await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=ResponseFormatJSONObject(type="json_object"),
                )
            raise
