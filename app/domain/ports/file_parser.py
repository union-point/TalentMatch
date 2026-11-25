from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol


class FileParser(ABC):
    @abstractmethod
    async def parse(self, file_path: Path) -> str:
        """Parse a file and return extracted text content."""
        ...


class FileParserSelector(Protocol):
    def __call__(self, filename: str, /, *, allow_plain_text: bool = False) -> FileParser: ...
