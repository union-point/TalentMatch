from app.config import settings
from app.domain.ports.ai_service import AIService


class AIServiceFactory:
    _registry: dict[str, type[AIService]] = {}
    _cache: dict[tuple[str, str], AIService] = {}

    @classmethod
    def register(cls, name: str, provider: type[AIService]) -> None:
        cls._registry[name] = provider

    @classmethod
    def create(cls, provider: str, model: str) -> AIService:
        key = (provider, model)
        instance = cls._cache.get(key)
        if instance is not None:
            return instance

        provider_cls = cls._registry.get(provider)
        if provider_cls is None:
            raise ValueError(f"No AI provider registered: {provider!r}")

        if provider == "openai":
            instance = provider_cls(
                model=model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        else:
            instance = provider_cls(model=model)

        cls._cache[key] = instance
        return instance
