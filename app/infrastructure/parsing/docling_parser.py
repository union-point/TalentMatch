import logging
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.core.exceptions import ParsingError
from app.domain.ports.file_parser import FileParser

logger = logging.getLogger(__name__)


class DoclingParser(FileParser):
    def __init__(self) -> None:
        pipeline_options = PdfPipelineOptions()
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
            },
        )

    async def parse(self, file_path: Path) -> str:
        try:
            result = self._converter.convert(str(file_path))
            document = result.document
            markdown_text = document.export_to_markdown()
            return self._normalize_text(markdown_text)
        except Exception as e:
            logger.error("Failed to parse file %s: %s", file_path, e)
            raise ParsingError(str(e)) from e

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
