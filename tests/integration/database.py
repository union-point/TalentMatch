from sqlalchemy.engine import URL, make_url


def validate_test_database_url(test_url: str, application_url: str) -> URL:
    """Fail closed before any connection to a database whose tables may be dropped."""
    target = make_url(test_url)
    application = make_url(application_url)
    name = target.database or ""
    if target.get_backend_name() != "postgresql" or not name.endswith("_test"):
        raise ValueError("TEST_DATABASE_URL must select a PostgreSQL database ending in '_test'")
    # Reject the application database name even with different credentials/host aliases.
    if name == application.database:
        raise ValueError("TEST_DATABASE_URL must not select the application database")
    # asyncpg query parameters can override connection parameters in the URL.
    if target.query:
        raise ValueError("TEST_DATABASE_URL must not contain query parameters")
    return target
