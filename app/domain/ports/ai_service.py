from abc import ABC, abstractmethod
from typing import Optional

from app.application.dto.ai import DeepAnalysisData, FastTrackResultData


class AIService(ABC):
    def __init__(
        self, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None
    ) -> None:
        """Initialize the AI service provider with configuration."""
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def analyze_fast_track(
        self, job_description: str, resume: str
    ) -> FastTrackResultData: ...

    @abstractmethod
    async def analyze_deep(self, job_description: str, resume: str) -> DeepAnalysisData: ...
