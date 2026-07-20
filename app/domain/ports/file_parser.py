from abc import ABC, abstractmethod
from pathlib import Path


class FileParser(ABC):
    @abstractmethod
    async def parse(self, file_path: Path) -> str:
        """Parse a file and return extracted text content."""
        ...
