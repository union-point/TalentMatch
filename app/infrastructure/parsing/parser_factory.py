from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError
from app.domain.ports.file_parser import FileParser
from app.infrastructure.parsing.docling_parser import DoclingParser
from app.infrastructure.parsing.plain_text_parser import PlainTextParser

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".png", ".jpg", ".jpeg", ".tiff"}
PLAIN_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}

_parser_instance: DoclingParser | None = None


def get_parser() -> FileParser:
    global _parser_instance  # noqa: PLW0603
    if _parser_instance is None:
        _parser_instance = DoclingParser()
    return _parser_instance


def get_parser_for_file(filename: str, *, allow_plain_text: bool = False) -> FileParser:
    extension = Path(filename).suffix.lower()
    if allow_plain_text and extension in PLAIN_TEXT_EXTENSIONS:
        return PlainTextParser()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(extension)
    return get_parser()
