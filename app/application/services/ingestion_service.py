import logging
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext
from pathlib import Path

from app.application.dto.ingestion import BatchIngestionResult, IngestionFailure, IngestionResponse
from app.core.exceptions import public_error_message
from app.domain.entities.job_description import JobDescription
from app.domain.entities.resume import Resume
from app.domain.ports.file_parser import FileParser, FileParserSelector
from app.domain.ports.file_storage import FileStorage
from app.domain.ports.repository import JobDescriptionRepository, ResumeRepository
from app.domain.value_objects import InjectionScanResult

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        jd_repository: JobDescriptionRepository,
        resume_repository: ResumeRepository,
        file_storage: FileStorage,
        organization_id: uuid.UUID,
        transaction: Callable[[], AbstractAsyncContextManager[object]] = nullcontext,
        *,
        parser_for_file: FileParserSelector,
        normalize_job_description: Callable[[str], str],
        normalize_resume: Callable[[str], str],
        scan_for_injection: Callable[[str], InjectionScanResult],
    ) -> None:
        self._organization_id = organization_id
        self._jd_repository = jd_repository
        self._resume_repository = resume_repository
        self._file_storage = file_storage
        self._transaction = transaction
        self._parser_for_file = parser_for_file
        self._normalize_job_description = normalize_job_description
        self._normalize_resume = normalize_resume
        self._scan_for_injection = scan_for_injection

    async def _ingest_job_description(
        self,
        stored_paths: list[Path],
        file_content: bytes,
        filename: str,
        title: str,
        company: str,
    ) -> IngestionResponse:
        parser = self._parser_for_file(filename, allow_plain_text=True)
        stored_path = await self._file_storage.save(file_content, filename, "jds")

        stored_paths.append(stored_path)
        raw_text = await self._parse_file(parser, stored_path)
        normalized = self._normalize_job_description(raw_text)
        injection_result = self._scan_for_injection(raw_text)

        jd = JobDescription(
            organization_id=self._organization_id,
            title=title,
            company=company,
            original_content=raw_text,
            normalized_content=normalized,
            file_path=str(stored_path),
            file_type=Path(filename).suffix.lower().lstrip("."),
            injection_scan_passed=injection_result.passed,
            injection_scan_details=injection_result.details,
        )
        saved = await self._jd_repository.save(jd)

        return IngestionResponse(
            id=saved.id,
            filename=filename,
            file_type=jd.file_type,
            original_content_length=len(raw_text),
            normalized_content_length=len(normalized),
            injection_scan=injection_result,
        )

    async def _ingest_resume(
        self,
        stored_paths: list[Path],
        file_content: bytes,
        filename: str,
        candidate_name: str | None = None,
        email: str | None = None,
    ) -> IngestionResponse:
        parser = self._parser_for_file(filename)
        stored_path = await self._file_storage.save(file_content, filename, "resumes")

        stored_paths.append(stored_path)
        raw_text = await self._parse_file(parser, stored_path)
        normalized = self._normalize_resume(raw_text)
        injection_result = self._scan_for_injection(raw_text)

        resume = Resume(
            organization_id=self._organization_id,
            filename=filename,
            original_content=raw_text,
            normalized_content=normalized,
            file_path=str(stored_path),
            file_type=Path(filename).suffix.lower().lstrip("."),
            injection_scan_passed=injection_result.passed,
            injection_scan_details=injection_result.details,
            candidate_name=candidate_name,
            email=email,
        )
        saved = await self._resume_repository.save(resume)

        return IngestionResponse(
            id=saved.id,
            filename=filename,
            file_type=resume.file_type,
            original_content_length=len(raw_text),
            normalized_content_length=len(normalized),
            injection_scan=injection_result,
        )

    @asynccontextmanager
    async def _atomic_upload(self) -> AsyncIterator[list[Path]]:
        stored_paths: list[Path] = []
        try:
            async with self._transaction():
                yield stored_paths
        except BaseException:
            for path in stored_paths:
                try:
                    await self._file_storage.delete(path)
                except Exception:
                    logger.exception("Could not remove failed upload %s", path)
            raise

    async def ingest_job_description(
        self,
        file_content: bytes,
        filename: str,
        title: str,
        company: str,
    ) -> IngestionResponse:
        async with self._atomic_upload() as paths:
            return await self._ingest_job_description(paths, file_content, filename, title, company)

    async def ingest_resume(
        self,
        file_content: bytes,
        filename: str,
        candidate_name: str | None = None,
        email: str | None = None,
    ) -> IngestionResponse:
        async with self._atomic_upload() as paths:
            return await self._ingest_resume(paths, file_content, filename, candidate_name, email)

    async def ingest_resumes_batch(
        self,
        files: list[tuple[bytes, str]],
    ) -> BatchIngestionResult:
        """Commit each resume independently and report safe, per-file failures."""
        result = BatchIngestionResult(resumes=[], errors=[])
        for index, (file_content, filename) in enumerate(files):
            try:
                resume = await self.ingest_resume(file_content, filename)
            except Exception as exc:
                logger.exception("Batch upload failed for file at index %s", index)
                result.errors.append(IngestionFailure(index, filename, public_error_message(exc)))
            else:
                result.resumes.append(resume)
        return result

    @staticmethod
    async def _parse_file(parser: FileParser, file_path: Path) -> str:
        return await parser.parse(file_path)
