import asyncio
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.application.dto.ingestion import IngestionResponse
from app.domain.value_objects import InjectionScanResult


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_html_content() -> str:
    return """<!DOCTYPE html>
<html>
<head><title>Software Engineer JD</title></head>
<body>
<h1>Software Engineer Position</h1>
<p>We are looking for a skilled software engineer with experience in Python and FastAPI.</p>
<ul>
<li>3+ years of experience</li>
<li>Strong knowledge of SQL databases</li>
<li>Experience with REST APIs</li>
</ul>
</body>
</html>"""


@pytest.fixture
def sample_resume_text() -> str:
    return """John Doe
Software Engineer
john@example.com

EXPERIENCE
Senior Software Engineer at TechCorp (2020-2024)
- Built REST APIs using Python and FastAPI
- Designed PostgreSQL database schemas
- Led a team of 4 developers

EDUCATION
B.S. Computer Science, MIT (2016-2020)

SKILLS
Python, FastAPI, SQLAlchemy, PostgreSQL, Docker, Kubernetes"""


@pytest.fixture
def sample_jd_text() -> str:
    return """Software Engineer Position

Company: Acme Inc
Location: Remote

Requirements:
- 3+ years of Python experience
- Experience with FastAPI or similar frameworks
- SQL database knowledge
- REST API design experience

Nice to have:
- Docker and Kubernetes experience
- Team leadership experience"""


def _make_ingestion_response(
    id_str: str = "550e8400-e29b-41d4-a716-446655440000",
    filename: str = "test.txt",
    file_type: str = "txt",
    original_length: int = 100,
    normalized_length: int = 90,
    injection_passed: bool = True,
) -> IngestionResponse:
    import uuid

    return IngestionResponse(
        id=uuid.UUID(id_str),
        filename=filename,
        file_type=file_type,
        original_content_length=original_length,
        normalized_content_length=normalized_length,
        injection_scan=InjectionScanResult(passed=injection_passed),
    )


@pytest_asyncio.fixture
async def client(temp_dir) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    from app.presentation.api.dependencies import get_ingestion_service

    mock_service = AsyncMock()

    async def mock_ingest_jd(file_content, filename, title, company):
        return _make_ingestion_response(
            filename=filename,
            file_type=filename.rsplit(".", 1)[-1] if "." in filename else "unknown",
            original_length=len(file_content),
            normalized_length=len(file_content) - 10,
        )

    async def mock_ingest_resume(file_content, filename, candidate_name=None, email=None):
        return _make_ingestion_response(
            filename=filename,
            file_type=filename.rsplit(".", 1)[-1] if "." in filename else "unknown",
            original_length=len(file_content),
            normalized_length=len(file_content) - 10,
        )

    async def mock_ingest_batch(files):
        results = []
        for content, filename in files:
            results.append(
                _make_ingestion_response(
                    filename=filename,
                    file_type=filename.rsplit(".", 1)[-1] if "." in filename else "unknown",
                    original_length=len(content),
                    normalized_length=len(content) - 10,
                )
            )
        return results

    mock_service.ingest_job_description = AsyncMock(side_effect=mock_ingest_jd)
    mock_service.ingest_resume = AsyncMock(side_effect=mock_ingest_resume)
    mock_service.ingest_resumes_batch = AsyncMock(side_effect=mock_ingest_batch)

    app.dependency_overrides[get_ingestion_service] = lambda: mock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
