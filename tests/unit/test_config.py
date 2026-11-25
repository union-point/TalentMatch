import pytest
from pydantic import ValidationError

from app.config import Settings


def test_openai_only_settings_allow_missing_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.setenv("AI_FAST_TRACK_PROVIDER", "openai")
    monkeypatch.setenv("AI_DEEP_ANALYSIS_PROVIDER", "openai")

    assert Settings(_env_file=None).gemini_api_key is None


@pytest.mark.parametrize(
    ("fast_track_provider", "deep_analysis_provider"), [("gemini", "openai"), ("openai", "gemini")]
)
@pytest.mark.parametrize("gemini_api_key", [None, "", "   "])
def test_gemini_settings_require_a_nonempty_key(
    fast_track_provider: str, deep_analysis_provider: str, gemini_api_key: str | None
) -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY is required"):
        Settings(
            _env_file=None,
            ai_fast_track_provider=fast_track_provider,
            ai_deep_analysis_provider=deep_analysis_provider,
            gemini_api_key=gemini_api_key,
        )
