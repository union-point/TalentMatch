Database-backed tests require an explicitly provisioned disposable PostgreSQL database:

```sh
TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost/talentmatch_test uv run pytest tests/integration
```

The database name must end in `_test` and differ from the configured application database name. Query parameters are rejected to prevent connection target overrides. These fixtures drop all application tables in the selected test database before and after each test; never put valuable data there or share it between concurrent test runs. Without `TEST_DATABASE_URL`, database-backed tests are skipped. Tests using mocked dependencies still run.
