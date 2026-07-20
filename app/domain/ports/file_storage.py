from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID


class FileStorage(ABC):
    @abstractmethod
    async def save(self, file_content: bytes, original_filename: str, subfolder: str) -> Path:
        """Save file content and return the stored file path."""
        ...

    @abstractmethod
    async def get_path(self, file_id: UUID, subfolder: str) -> Path:
        """Return the stored file path for a given file ID."""
        ...
