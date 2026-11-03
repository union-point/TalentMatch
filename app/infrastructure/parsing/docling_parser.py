import logging
from pathlib import Path
from threading import Lock

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.core.exceptions import ParsingError
from app.domain.ports.file_parser import FileParser

logger = logging.getLogger(__name__)


class DoclingParser(FileParser):
    def __init__(self) -> None:
        self._conversion_lock = Lock()
        pipeline_options = PdfPipelineOptions(document_timeout=settings.document_timeout_seconds)
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True

        self._converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.IMAGE,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
            },
        )

    async def parse(self, file_path: Path) -> str:
        return await run_in_threadpool(self._parse_sync, file_path)

    def _parse_sync(self, file_path: Path) -> str:
        try:
            with self._conversion_lock:
                return self._convert(file_path)
        except Exception as e:
            logger.error("Failed to parse file %s: %s", file_path, e)
            raise ParsingError(str(e)) from e

    def _convert(self, file_path: Path) -> str:
        result = self._converter.convert(
            str(file_path),
            max_num_pages=settings.max_document_pages,
            max_file_size=settings.max_upload_file_bytes,
        )
        if result.status != ConversionStatus.SUCCESS:
            raise ParsingError("Document conversion did not complete")
        markdown_text = result.document.export_to_markdown()
        return self._normalize_text(markdown_text)

    @staticmethod
    def _normalize_text(text: str) -> str:
        import re
        import unicodedata

        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" +\n", "\n", text)
        return text.strip()
