from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError
from app.domain.ports.file_parser import FileParser
from app.infrastructure.parsing.docling_parser import DoclingParser

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".png", ".jpg", ".jpeg", ".tiff"}

_parser_instance: DoclingParser | None = None


def get_parser() -> FileParser:
    global _parser_instance  # noqa: PLW0603
    if _parser_instance is None:
        _parser_instance = DoclingParser()
    return _parser_instance


def get_parser_for_file(filename: str) -> FileParser:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(extension)
    return get_parser()
