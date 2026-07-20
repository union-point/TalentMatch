from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.application.dto.ai import DeepAnalysisData, EvidenceItem, FastTrackResultData
from app.core.exceptions import AIResponseError
from app.infrastructure.ai.gemini_service import GeminiService


@pytest.fixture
def sample_jd_text() -> str:
    return "Software Engineer with 3+ years of Python and FastAPI experience."


@pytest.fixture
def sample_resume_text() -> str:
    return "Experienced Python developer with FastAPI and PostgreSQL skills."


@pytest.fixture
def mock_genai_client():
    with patch(
        "app.infrastructure.ai.gemini_service.genai.Client", autospec=True
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock()
        mock_client_cls.return_value = mock_client
        yield mock_client.aio.models


def _make_mock_response(
    parsed: object,
    text: str = "",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
):
    response = MagicMock()
    response.parsed = parsed
    response.text = text

    usage_metadata = MagicMock()
    usage_metadata.prompt_token_count = prompt_tokens
    usage_metadata.candidates_token_count = completion_tokens
    usage_metadata.total_token_count = prompt_tokens + completion_tokens
    response.usage_metadata = usage_metadata

    return response


class TestGeminiServiceFastTrack:
    async def test_returns_valid_fast_track_result(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        fast_track_data = FastTrackResultData(pass_fail=True, score=85, explanation="Great match")
        mock_response = _make_mock_response(parsed=fast_track_data)
        mock_genai_client.generate_content.return_value = mock_response

        service = GeminiService()
        result = await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        assert isinstance(result, FastTrackResultData)
        assert result.pass_fail is True
        assert result.score == 85
        assert result.explanation == "Great match"

    async def test_returns_failing_fast_track_result(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        fast_track_data = FastTrackResultData(pass_fail=False, score=35, explanation="Poor match")
        mock_response = _make_mock_response(parsed=fast_track_data)
        mock_genai_client.generate_content.return_value = mock_response

        service = GeminiService()
        result = await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        assert result.pass_fail is False
        assert result.score == 35

    async def test_uses_correct_model_and_config(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        fast_track_data = FastTrackResultData(pass_fail=True, score=80, explanation="Good match")
        mock_response = _make_mock_response(parsed=fast_track_data)
        mock_genai_client.generate_content.return_value = mock_response

        service = GeminiService()
        await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        mock_genai_client.generate_content.assert_called_once()
        call_kwargs = mock_genai_client.generate_content.call_args.kwargs
        assert call_kwargs["config"].response_mime_type == "application/json"
        assert call_kwargs["config"].response_schema == FastTrackResultData


class TestGeminiServiceDeep:
    async def test_returns_valid_deep_analysis(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        deep_data = DeepAnalysisData(
            overall_score=88,
            strengths=["Python expertise", "FastAPI experience"],
            weaknesses=["No cloud experience"],
            risks=["None"],
            detailed_reasoning="Strong match overall.",
            evidence=[
                EvidenceItem(
                    text="Built REST APIs using Python and FastAPI",
                    category="experience",
                )
            ],
        )
        mock_response = _make_mock_response(parsed=deep_data)
        mock_genai_client.generate_content.return_value = mock_response

        service = GeminiService()
        result = await service.analyze_deep(sample_jd_text, sample_resume_text)

        assert isinstance(result, DeepAnalysisData)
        assert result.overall_score == 88
        assert len(result.strengths) == 2
        assert len(result.weaknesses) == 1
        assert len(result.evidence) == 1
        assert result.evidence[0].category == "experience"

    async def test_uses_correct_schema_for_deep(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        deep_data = DeepAnalysisData(
            overall_score=70,
            strengths=[],
            weaknesses=[],
            risks=[],
            detailed_reasoning="OK",
            evidence=[],
        )
        mock_response = _make_mock_response(parsed=deep_data)
        mock_genai_client.generate_content.return_value = mock_response

        service = GeminiService()
        await service.analyze_deep(sample_jd_text, sample_resume_text)

        call_kwargs = mock_genai_client.generate_content.call_args.kwargs
        assert call_kwargs["config"].response_schema == DeepAnalysisData


class TestGeminiServiceErrorHandling:
    async def test_empty_parsed_response_raises_error(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        mock_response = _make_mock_response(parsed=None, text="Some raw text")
        mock_genai_client.generate_content.return_value = mock_response

        service = GeminiService()
        with pytest.raises(AIResponseError, match="empty parsed response"):
            await service.analyze_fast_track(sample_jd_text, sample_resume_text)

    async def test_malformed_schema_raises_validation_error(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        bad_data = {"pass_fail": "not_a_bool", "score": "not_an_int"}
        mock_response = _make_mock_response(parsed=bad_data)
        mock_genai_client.generate_content.return_value = mock_response

        service = GeminiService()
        with pytest.raises(ValidationError):
            await service.analyze_fast_track(sample_jd_text, sample_resume_text)

    async def test_retry_on_timeout(self, mock_genai_client, sample_jd_text, sample_resume_text):
        fast_track_data = FastTrackResultData(pass_fail=True, score=90, explanation="Good")
        successful_response = _make_mock_response(parsed=fast_track_data)

        mock_genai_client.generate_content.side_effect = [
            TimeoutError("timeout"),
            TimeoutError("timeout"),
            successful_response,
        ]

        service = GeminiService()
        result = await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        assert isinstance(result, FastTrackResultData)
        assert mock_genai_client.generate_content.call_count == 3

    async def test_all_retries_exhausted_raises_error(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        mock_genai_client.generate_content.side_effect = TimeoutError("timeout")

        service = GeminiService()
        with pytest.raises(AIResponseError, match="failed after 3 attempts"):
            await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        assert mock_genai_client.generate_content.call_count == 3

    async def test_non_retryable_4xx_error_raises_immediately(
        self, mock_genai_client, sample_jd_text, sample_resume_text
    ):
        from google.genai.errors import APIError

        api_error = APIError(code=400, response_json={"error": "Bad request"})
        mock_genai_client.generate_content.side_effect = api_error

        service = GeminiService()
        with pytest.raises(AIResponseError, match="Non-retryable"):
            await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        assert mock_genai_client.generate_content.call_count == 1

    async def test_retry_on_rate_limit(self, mock_genai_client, sample_jd_text, sample_resume_text):
        from google.genai.errors import APIError

        fast_track_data = FastTrackResultData(pass_fail=True, score=75, explanation="OK")
        successful_response = _make_mock_response(parsed=fast_track_data)

        rate_limit_error = APIError(code=429, response_json={"error": "Rate limited"})
        mock_genai_client.generate_content.side_effect = [
            rate_limit_error,
            successful_response,
        ]

        service = GeminiService()
        result = await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        assert isinstance(result, FastTrackResultData)
        assert mock_genai_client.generate_content.call_count == 2

    async def test_retry_on_5xx_error(self, mock_genai_client, sample_jd_text, sample_resume_text):
        from google.genai.errors import APIError

        fast_track_data = FastTrackResultData(pass_fail=True, score=70, explanation="Acceptable")
        successful_response = _make_mock_response(parsed=fast_track_data)

        server_error = APIError(code=503, response_json={"error": "Service unavailable"})
        mock_genai_client.generate_content.side_effect = [
            server_error,
            successful_response,
        ]

        service = GeminiService()
        result = await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        assert isinstance(result, FastTrackResultData)
        assert mock_genai_client.generate_content.call_count == 2


class TestGeminiServiceLogging:
    async def test_token_usage_logged(
        self, mock_genai_client, sample_jd_text, sample_resume_text, caplog
    ):
        import logging

        caplog.set_level(logging.INFO)

        fast_track_data = FastTrackResultData(pass_fail=True, score=80, explanation="Good")
        mock_response = _make_mock_response(
            parsed=fast_track_data, prompt_tokens=150, completion_tokens=75
        )
        mock_genai_client.generate_content.return_value = mock_response

        service = GeminiService()
        await service.analyze_fast_track(sample_jd_text, sample_resume_text)

        assert any("Gemini fast_track tokens:" in record.message for record in caplog.records)
        assert any("prompt=150" in record.message for record in caplog.records)
        assert any("completion=75" in record.message for record in caplog.records)
        assert any("total=225" in record.message for record in caplog.records)


class TestAIServicePort:
    async def test_abstract_class_cannot_be_instantiated(self):
        from app.domain.ports.ai_service import AIService

        with pytest.raises(TypeError):
            AIService()  # type: ignore[abstract]

    async def test_gemini_service_is_instance_of_port(self, mock_genai_client):
        service = GeminiService()
        from app.domain.ports.ai_service import AIService

        assert isinstance(service, AIService)
