# TalentMatch

AI-powered resume screening API. Upload job descriptions and resumes, run batch fit scoring, request async deep analysis, and rank candidates.

**Stack:** FastAPI · Python 3.13 · PostgreSQL 16 · Redis · Celery · Docling · Gemini/OpenAI · React 19 + Vite

## Features

- **Document ingestion** — PDF, DOCX, HTML via Docling (layout analysis, tables, OCR). Text normalized and stored with original files on disk.
- **Prompt-injection scanning** — Unicode invisible-char detection, entropy checks, known jailbreak phrases, hidden-content heuristics. Suspicion score (0–100); threshold 15.
- **Fast-track analysis** — Concurrent JD↔resume scoring (0–100, pass/fail, explanation). Max 5 concurrent LLM calls; partial failures isolated per resume.
- **Deep analysis** — Async Celery job: strengths, weaknesses, risks, evidence excerpts, detailed reasoning. Status: `pending` → `in_progress` → `completed` | `failed`.
- **Dashboard API** — Ranked candidates per JD with filters (`min_score`, `pass_fail_only`, name search), pagination, candidate detail, resume file download.
- **Swappable AI providers** — Gemini and OpenAI-compatible backends via factory; independent provider/model for fast-track vs deep analysis.

## Architecture

Clean Architecture with dependency inversion:

```
Presentation  →  Application  →  Domain  ←  Infrastructure
(FastAPI)        (services)      (entities, ports)   (SQLAlchemy, AI, Docling, storage)
```

| Pipeline | Flow |
|----------|------|
| Ingestion | Upload → parse → normalize → injection scan → persist |
| Fast-track | JD + resume IDs → concurrent LLM → store results |
| Deep analysis | Create pending record → Celery worker → LLM → poll |

Domain has zero framework imports. Ports (`AIService`, `FileParser`, `FileStorage`, repositories) are implemented in infrastructure.

## Quick start

### Prerequisites

- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) (local backend without full Docker)
- Node 20+ (frontend)
- Gemini API key (or OpenAI-compatible key)

### Docker (API + worker + deps)

```bash
cp .env.example .env
# set GEMINI_API_KEY in .env

make build          # build images, start postgres/redis/app/worker
make migrate        # alembic upgrade head
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| OpenAPI docs | http://localhost:8000/docs |
| Health | `GET /health` → `{"status":"ok"}` |

### Frontend

```bash
cd frontend
npm install
npm run dev         # http://localhost:5173 — proxies /api → :8000
```

### Local API (infra in Docker)

```bash
docker compose up -d postgres redis
cp .env.example .env   # DATABASE_URL/REDIS_URL point at localhost

uv sync
uv run alembic upgrade head
make dev               # uvicorn --reload :8000

# separate terminal — required for deep analysis
uv run celery -A app.tasks.celery_app:celery_app worker --loglevel=info
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | yes | `postgresql+asyncpg://...` |
| `GEMINI_API_KEY` | yes* | Gemini key (*if using Gemini) |
| `REDIS_URL` | yes | Celery broker |
| `UPLOAD_DIR` | no | Default `./uploads` |
| `CORS_ORIGINS` | yes | JSON list, e.g. `["http://localhost:5173"]` |
| `LOG_LEVEL` | no | Default `INFO` |
| `AI_FAST_TRACK_PROVIDER` | no | `gemini` (default) or `openai` |
| `AI_FAST_TRACK_MODEL` | no | Default `gemini-3.1-flash-lite` |
| `AI_DEEP_ANALYSIS_PROVIDER` | no | `gemini` or `openai` |
| `AI_DEEP_ANALYSIS_MODEL` | no | Default `gemini-3.1-flash-lite` |
| `OPENAI_API_KEY` | if openai | — |
| `OPENAI_BASE_URL` | no | Default `https://api.openai.com/v1` |

OpenAI-compatible example:

```env
AI_FAST_TRACK_PROVIDER=openai
AI_FAST_TRACK_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

## API

Interactive schema: `/docs`. Base path `/api/v1`.

### Ingestion

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/job-descriptions/upload` | multipart: `file`, `title`, `company` |
| `GET` | `/job-descriptions` | list JDs |
| `GET` | `/job-descriptions/{id}` | JD detail + scan |
| `POST` | `/resumes/upload` | multipart resume |
| `POST` | `/resumes/batch-upload` | multiple resumes |

### Analysis

```bash
# Fast-track (sync batch)
curl -s -X POST http://localhost:8000/api/v1/analysis/fast-track \
  -H 'Content-Type: application/json' \
  -d '{"job_description_id":"<jd-uuid>","resume_ids":["<resume-uuid>"]}'

# Deep analysis (async — 202)
curl -s -X POST http://localhost:8000/api/v1/analysis/deep \
  -H 'Content-Type: application/json' \
  -d '{"resume_id":"<resume-uuid>","job_description_id":"<jd-uuid>"}'
# → {"analysis_id":"...","status":"pending"}

curl -s http://localhost:8000/api/v1/analysis/deep/<analysis_id>
```

### Dashboard

| Method | Path | Query |
|--------|------|--------|
| `GET` | `/dashboard/jobs/{jd_id}/candidates` | `min_score`, `pass_fail_only`, `q`, `page`, `page_size` |
| `GET` | `/dashboard/candidates/{resume_id}/job/{jd_id}` | detail (fast-track + deep) |
| `GET` | `/dashboard/candidates/{resume_id}/resume-file` | original file download |

## Typical workflow

1. Upload JD → receive `jd_id`
2. Upload one or more resumes → receive `resume_id`s
3. `POST /analysis/fast-track` with JD + resume IDs → scores
4. Optionally `POST /analysis/deep` for shortlisted candidates; poll until `completed`
5. Rank/filter via dashboard endpoints or the React UI

## Project layout

```
app/
  domain/           # entities, value objects, ports
  application/      # services + DTOs
  infrastructure/   # DB, AI, parsing, security, storage
  presentation/     # routes, schemas, middleware
  tasks/            # Celery deep-analysis worker
frontend/           # React SPA (Vite, TanStack Query, Tailwind)
alembic/            # migrations
tests/              # unit + integration
```

## Development

```bash
make up               # start stack
make migrate
make test             # unit + integration (in app container)
make test-coverage
make lint             # ruff
make format
make typecheck        # mypy (strict)
make logs-app
make logs-worker
```

Local tests without Docker app container: `uv run pytest` (integration tests need Postgres; marked `integration`).

## Notes

- Docling downloads model artifacts on first parse (cold start).
- Deep analysis requires a running Celery worker and Redis.
- Alembic migrations need a live Postgres instance.
