import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext
from pathlib import Path

from app.application.dto.ingestion import IngestionResponse
from app.domain.entities.job_description import JobDescription
from app.domain.entities.resume import Resume
from app.domain.ports.file_parser import FileParser
from app.domain.ports.file_storage import FileStorage
from app.domain.ports.repository import JobDescriptionRepository, ResumeRepository
from app.infrastructure.parsing.parser_factory import get_parser_for_file
from app.infrastructure.parsing.text_normalizer import normalize_text, strip_markdown_formatting
from app.infrastructure.security.prompt_injection_detector import detect_injection

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        jd_repository: JobDescriptionRepository,
        resume_repository: ResumeRepository,
        file_storage: FileStorage,
        transaction: Callable[[], AbstractAsyncContextManager[object]] = nullcontext,
    ) -> None:
        self._jd_repository = jd_repository
        self._resume_repository = resume_repository
        self._file_storage = file_storage
        self._transaction = transaction

    async def _ingest_job_description(
        self,
        stored_paths: list[Path],
        file_content: bytes,
        filename: str,
        title: str,
        company: str,
    ) -> IngestionResponse:
        parser = get_parser_for_file(filename)
        stored_path = await self._file_storage.save(file_content, filename, "jds")

        stored_paths.append(stored_path)
        raw_text = await self._parse_file(parser, stored_path)
        normalized = normalize_text(raw_text)
        injection_result = detect_injection(raw_text)

        jd = JobDescription(
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
        parser = get_parser_for_file(filename)
        stored_path = await self._file_storage.save(file_content, filename, "resumes")

        stored_paths.append(stored_path)
        raw_text = await self._parse_file(parser, stored_path)
        normalized = strip_markdown_formatting(raw_text)
        injection_result = detect_injection(raw_text)

        resume = Resume(
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
    ) -> list[IngestionResponse]:
        """Commit all resumes together, or roll back and delete every saved file."""
        async with self._atomic_upload() as paths:
            results: list[IngestionResponse] = []
            for file_content, filename in files:
                results.append(await self._ingest_resume(paths, file_content, filename))
            return results

    @staticmethod
    async def _parse_file(parser: FileParser, file_path: Path) -> str:
        return await parser.parse(file_path)
