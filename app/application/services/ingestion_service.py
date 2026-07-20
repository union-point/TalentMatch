import logging
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
    ) -> None:
        self._jd_repository = jd_repository
        self._resume_repository = resume_repository
        self._file_storage = file_storage

    async def ingest_job_description(
        self,
        file_content: bytes,
        filename: str,
        title: str,
        company: str,
    ) -> IngestionResponse:
        parser = get_parser_for_file(filename)
        stored_path = await self._file_storage.save(file_content, filename, "jds")

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

    async def ingest_resume(
        self,
        file_content: bytes,
        filename: str,
        candidate_name: str | None = None,
        email: str | None = None,
    ) -> IngestionResponse:
        parser = get_parser_for_file(filename)
        stored_path = await self._file_storage.save(file_content, filename, "resumes")

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

    async def ingest_resumes_batch(
        self,
        files: list[tuple[bytes, str]],
    ) -> list[IngestionResponse]:
        results: list[IngestionResponse] = []
        for file_content, filename in files:
            result = await self.ingest_resume(file_content, filename)
            results.append(result)
        return results

    @staticmethod
    async def _parse_file(parser: FileParser, file_path: Path) -> str:
        return await parser.parse(file_path)
