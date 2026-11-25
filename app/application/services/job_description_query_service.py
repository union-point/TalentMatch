import uuid

from app.domain.entities.job_description import JobDescription
from app.domain.ports.repository import JobDescriptionRepository


class JobDescriptionQueryService:
    def __init__(self, repository: JobDescriptionRepository) -> None:
        self._repository = repository

    async def list_job_descriptions(self) -> list[JobDescription]:
        return await self._repository.get_all()

    async def get_job_description(self, jd_id: uuid.UUID) -> JobDescription | None:
        return await self._repository.get_by_id(jd_id)
