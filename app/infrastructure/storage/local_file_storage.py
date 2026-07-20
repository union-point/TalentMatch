import functools
import uuid
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.core.exceptions import FileNotFoundError
from app.domain.ports.file_storage import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir or settings.upload_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, file_content: bytes, original_filename: str, subfolder: str) -> Path:
        target_dir = self._base_dir / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        extension = Path(original_filename).suffix
        file_id = uuid.uuid4()
        filename = f"{file_id}{extension}"
        file_path = target_dir / filename

        file_path.write_bytes(file_content)
        return file_path

    async def get_path(self, file_id: UUID, subfolder: str) -> Path:
        target_dir = self._base_dir / subfolder
        if not target_dir.exists():
            raise FileNotFoundError(str(file_id))

        for file_path in target_dir.iterdir():
            if file_path.stem == str(file_id):
                return file_path

        raise FileNotFoundError(str(file_id))


@functools.cache
def get_local_file_storage() -> LocalFileStorage:
    return LocalFileStorage()
