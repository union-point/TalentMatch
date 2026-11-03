from unittest.mock import patch

import pytest

from tests.integration.database import validate_test_database_url


@pytest.mark.parametrize("application_name", ["talentmatch_db", "production", "production_test"])
async def test_fixture_rejects_application_database_before_connecting(
    application_name: str,
) -> None:
    from tests.integration.conftest import engine

    url = f"postgresql+asyncpg://localhost/{application_name}"
    with (
        patch.dict("os.environ", {"TEST_DATABASE_URL": url}),
        patch("tests.integration.conftest.settings") as settings,
        patch("tests.integration.conftest.create_async_engine") as connect,
    ):
        settings.database_url = url
        fixture = engine.__wrapped__()
        with pytest.raises(ValueError):
            await anext(fixture)
        connect.assert_not_called()


@pytest.mark.parametrize(
    "test_url",
    [
        "postgresql+asyncpg://localhost/production",
        "postgresql+asyncpg://localhost/",
        "sqlite+aiosqlite:///safe_test",
        "postgresql+asyncpg://localhost/safe_test?database=production",
    ],
)
def test_rejects_unsafe_targets(test_url: str) -> None:
    with pytest.raises(ValueError):
        validate_test_database_url(test_url, "postgresql+asyncpg://localhost/production")


def test_accepts_explicit_dedicated_database() -> None:
    url = "postgresql+asyncpg://localhost/talentmatch_test"
    assert str(validate_test_database_url(url, "postgresql+asyncpg://localhost/custom_name")) == url


async def test_fixture_skips_without_explicit_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.integration.conftest import engine

    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with patch("tests.integration.conftest.create_async_engine") as connect:
        fixture = engine.__wrapped__()
        with pytest.raises(pytest.skip.Exception):
            await anext(fixture)
        connect.assert_not_called()
