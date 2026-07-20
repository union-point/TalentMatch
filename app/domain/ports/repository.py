import uuid
from abc import ABC, abstractmethod

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.entities.job_description import JobDescription
from app.domain.entities.resume import Resume


class JobDescriptionRepository(ABC):
    @abstractmethod
    async def save(self, jd: JobDescription) -> JobDescription: ...

    @abstractmethod
    async def get_by_id(self, jd_id: uuid.UUID) -> JobDescription | None: ...

    @abstractmethod
    async def get_all(self) -> list[JobDescription]: ...


class ResumeRepository(ABC):
    @abstractmethod
    async def save(self, resume: Resume) -> Resume: ...

    @abstractmethod
    async def get_by_id(self, resume_id: uuid.UUID) -> Resume | None: ...

    @abstractmethod
    async def update(self, resume: Resume) -> Resume: ...


class FastTrackRepository(ABC):
    @abstractmethod
    async def save(self, result: FastTrackResult) -> FastTrackResult: ...

    @abstractmethod
    async def get_by_id(self, result_id: uuid.UUID) -> FastTrackResult | None: ...

    @abstractmethod
    async def get_by_job_description_id(
        self, jd_id: uuid.UUID
    ) -> list[FastTrackResult]: ...


class DeepAnalysisRepository(ABC):
    @abstractmethod
    async def save(self, analysis: DeepAnalysis) -> DeepAnalysis: ...

    @abstractmethod
    async def get_by_id(self, analysis_id: uuid.UUID) -> DeepAnalysis | None: ...

    @abstractmethod
    async def get_by_resume_and_jd(
        self, resume_id: uuid.UUID, jd_id: uuid.UUID
    ) -> DeepAnalysis | None: ...
