import asyncio
import threading
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from docling.datamodel.base_models import ConversionStatus

from app.core.exceptions import ParsingError
from app.infrastructure.parsing.docling_parser import DoclingParser
from app.infrastructure.storage.local_file_storage import LocalFileStorage


def test_incomplete_document_is_rejected_without_exporting_text(tmp_path: Path) -> None:
    parser = DoclingParser.__new__(DoclingParser)
    parser._conversion_lock = threading.Lock()
    parser._converter = MagicMock()
    result = parser._converter.convert.return_value
    result.status = ConversionStatus.PARTIAL_SUCCESS
    with pytest.raises(ParsingError, match="did not complete"):
        parser._parse_sync(tmp_path / "resume.pdf")
    result.document.export_to_markdown.assert_not_called()


async def test_conversion_leaves_event_loop_responsive(tmp_path: Path) -> None:
    parser = DoclingParser.__new__(DoclingParser)
    parser._conversion_lock = threading.Lock()
    parser._converter = MagicMock()
    started, release = threading.Event(), threading.Event()
    loop_thread = threading.get_ident()

    def convert(path: str, **kwargs: int) -> MagicMock:
        assert threading.get_ident() != loop_thread
        started.set()
        assert release.wait(timeout=5)
        result = MagicMock()
        result.status = ConversionStatus.SUCCESS
        result.document.export_to_markdown.return_value = "  hello   world  "
        return result

    parser._converter.convert.side_effect = convert
    task = asyncio.create_task(parser.parse(tmp_path / "resume.pdf"))
    try:
        async with asyncio.timeout(3):
            while not started.is_set():
                await asyncio.sleep(0.01)
            assert not task.done()
    finally:
        release.set()
    assert await task == "hello world"
    parser._converter.convert.side_effect = ValueError("invalid document")
    with pytest.raises(ParsingError, match="invalid document"):
        await parser.parse(tmp_path / "bad.pdf")


async def test_storage_runs_filesystem_operations_off_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = LocalFileStorage(tmp_path / "new")
    loop_thread = threading.get_ident()
    original_write = Path.write_bytes
    original_iterdir = Path.iterdir

    def write(path: Path, data: bytes) -> int:
        assert threading.get_ident() != loop_thread
        return original_write(path, data)

    def iterdir(path: Path) -> Iterator[Path]:
        assert threading.get_ident() != loop_thread
        return original_iterdir(path)

    monkeypatch.setattr(Path, "write_bytes", write)
    monkeypatch.setattr(Path, "iterdir", iterdir)
    path = await storage.save(b"resume", "resume.pdf", "resumes")
    assert path.read_bytes() == b"resume"
    from uuid import UUID

    assert await storage.get_path(UUID(path.stem), "resumes") == path
