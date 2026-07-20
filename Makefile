.PHONY: dev migrate test test-coverage test-integration lint format typecheck \
        up down build restart ps logs-app logs-worker logs-db redis db
dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	docker compose exec app uv run alembic upgrade head

test-coverage:
	docker compose exec app uv run pytest --cov=app --cov-report=term-missing

test-integration:
	docker compose exec app uv run pytest tests/integration/

test:
	docker compose exec app uv run pytest

lint:
	docker compose exec app uv run ruff check .

format:
	docker compose exec app uv run ruff format .

typecheck:
	docker compose exec app uv run mypy app

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose up -d --build

restart:
	docker compose restart

ps:
	docker compose ps

logs-app:
	docker compose logs -f app

logs-worker:
	docker compose logs -f worker

logs-db:
	docker compose logs -f postgres

redis:
	docker compose exec redis redis-cli

db:
	docker compose exec postgres psql -U talentmatch_user -d talentmatch_db