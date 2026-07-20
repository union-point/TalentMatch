from app.infrastructure.ai.ai_factory import AIServiceFactory
from app.infrastructure.ai.gemini_service import GeminiService
from app.infrastructure.ai.openai_service import OpenAIService

AIServiceFactory.register("gemini", GeminiService)
AIServiceFactory.register("openai", OpenAIService)

__all__ = ["AIServiceFactory"]
