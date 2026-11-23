from codecs import BOM_UTF16_BE, BOM_UTF16_LE
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from app.core.exceptions import ParsingError
from app.domain.ports.file_parser import FileParser
from app.infrastructure.parsing.text_normalizer import normalize_text


class PlainTextParser(FileParser):
    async def parse(self, file_path: Path) -> str:
        content = await run_in_threadpool(file_path.read_bytes)
        encoding = "utf-16" if content.startswith((BOM_UTF16_BE, BOM_UTF16_LE)) else "utf-8-sig"
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError as exc:
            raise ParsingError("Use a UTF-8 or UTF-16 text document.") from exc

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if "\x00" in text or not normalize_text(text):
            raise ParsingError("The text document contains no readable content.")
        return text
