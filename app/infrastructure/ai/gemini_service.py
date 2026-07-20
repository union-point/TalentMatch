import asyncio
import logging
import random
from typing import TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel

from app.application.dto.ai import DeepAnalysisData, FastTrackResultData
from app.config import settings
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


class GeminiService(AIService):
    def __init__(self, model: str = "gemini-3.5-flash") -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = model
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

                if response.usage_metadata:
                    logger.info(
                        "Gemini %s tokens: prompt=%s, completion=%s, total=%s",
                        prompt_type,
                        response.usage_metadata.prompt_token_count,
                        response.usage_metadata.candidates_token_count,
                        response.usage_metadata.total_token_count,
                    )

                if response.parsed is None:
                    raise AIResponseError(
                        "Gemini returned empty parsed response",
                        raw_response=response.text if hasattr(response, "text") else "",
                    )

                return schema.model_validate(response.parsed)

            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    "Gemini %s attempt %d timed out after %ds",
                    prompt_type,
                    attempt + 1,
                    timeout,
                )
            except genai_errors.APIError as e:
                last_exception = e
                logger.warning(
                    "Gemini %s attempt %d failed: %s",
                    prompt_type,
                    attempt + 1,
                    e,
                )

                if getattr(e, "code", None) is not None and 400 <= e.code < 500 and e.code != 429:
                    raise AIResponseError(f"Non-retryable API error: {e}", raw_response=str(e))

            if attempt < MAX_RETRIES - 1:
                delay = (BASE_DELAY * (2**attempt)) + random.uniform(0, 1)
                logger.info("Retrying Gemini %s in %.2f seconds...", prompt_type, delay)
                await asyncio.sleep(delay)

        raise AIResponseError(
            f"Gemini {prompt_type} failed after {MAX_RETRIES} attempts",
            raw_response=str(last_exception),
        )

    async def _make_api_call(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> genai_types.GenerateContentResponse:
        return await self._client.aio.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
