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
- Python 3 to generate a development encryption key
- [uv](https://docs.astral.sh/uv/) if running the backend on the host
- Node 20+ (frontend)
- Gemini API key (or OpenAI-compatible key)

### Configure `.env`

From the project root, copy `.env.example` to `.env` if you don't already have
one. For Gemini in both analysis modes, set `GEMINI_API_KEY` and
`AI_DEEP_ANALYSIS_PROVIDER=gemini`. See [Configuration](#configuration) for
OpenAI-compatible settings.

For a new setup, run the command below and replace `AUTH_ENCRYPTION_KEYS=[]` in
`.env` with the generated line. Reuse your existing key if you already have one.

```bash
python3 -c 'import base64, json, secrets; print("AUTH_ENCRYPTION_KEYS=" + json.dumps([base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()]))'
```

### Docker backend

Compose runs FastAPI (`app`), the Celery worker, Celery beat, Postgres, Redis,
and Mailpit. Set the following URLs in `.env` if you're using the default Compose
database credentials.

```env
DATABASE_URL=postgresql+asyncpg://talentmatch_user:talentmatch_pass@postgres:5432/talentmatch_db
REDIS_URL=redis://redis:6379/0
```

Compose sets the SMTP address to `mailpit:1025`. Keep
`PUBLIC_ORIGIN=http://localhost:5173` for the Vite frontend.

```bash
make up             # docker compose up -d
make migrate        # apply migrations inside the app container
```

`make up` builds missing backend images and reuses existing ones. Use
`make build` after changing the Dockerfile or backend dependencies, or when you
want to rebuild the images. It runs `docker compose up -d --build`, which builds
and starts the services in one step.

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| OpenAPI docs | http://localhost:8000/docs |
| Health | `GET /health` → `{"status":"ok"}` |
| Mailpit inbox | http://localhost:8026 |

### Frontend

```bash
cd frontend
npm install
npm run dev         # http://localhost:5173 — proxies /api → :8000
```

### Local backend (Postgres, Redis, and Mailpit in Docker)

Use this workflow to run and debug the Python processes on your machine. Use the
`localhost` database, Redis, and SMTP addresses from `.env.example`. Compose
starts the dependencies, and you start FastAPI, the worker, and beat on the host.
In `.env`, quote the display name and address together as
`SMTP_FROM="TalentMatch <no-reply@localhost>"` so `uv --env-file` can parse it.

```bash
docker compose up -d --wait postgres redis mailpit
uv sync
uv run --env-file .env alembic upgrade head
make dev

# In separate terminals from the project root
uv run celery -A app.tasks.celery_app:celery_app worker --loglevel=info
uv run celery -A app.tasks.celery_app:celery_app beat --loglevel=info
```

Both Celery processes are needed for verification emails and deep analysis.
Start the [frontend](#frontend) the same way for either backend workflow.

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
| `AI_DEEP_ANALYSIS_PROVIDER` | no | `openai` (default) or `gemini` |
| `AI_DEEP_ANALYSIS_MODEL` | no | Default `gemini-3.1-flash-lite` |
| `OPENAI_API_KEY` | if openai | — |
| `OPENAI_BASE_URL` | no | Default `http://host.docker.internal:8080/v1`. Set a URL reachable from the API for fast-track and from the worker for deep analysis. |

OpenAI-compatible example:

```env
AI_FAST_TRACK_PROVIDER=openai
AI_FAST_TRACK_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
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
| `GET` | `/dashboard/jobs/{jd_id}/candidates` | `min_score`, `status`, `sort_by`, `sort_direction`, `q`, `page`, `page_size` |
| `GET` | `/dashboard/candidates/{resume_id}/job/{jd_id}` | detail (fast-track + deep) |
| `GET` | `/dashboard/candidates/{resume_id}/resume-file` | original file download |

Candidate lists paginate and filter on the server. `q` searches names and emails;
`status` accepts `all`, `pass`, or `fail`; `sort_by` accepts `score`,
`candidate_name`, or `pass_fail`, with `sort_direction=asc|desc`. The legacy
`pass_fail_only=true` parameter still applies when `status=all`.

Unscored uploads are available at `GET /dashboard/jobs/{jd_id}/unscored-resumes`
(`page`, `page_size`, `q`). Both screens show organization-owned resumes without a
score for the selected job, including older uploads and failed scoring attempts.
Select resumes there to analyze them; successful results move to the candidate
list. The dashboard keeps its selected job in the URL so refresh preserves context.

## Typical workflow

1. Upload JD → receive `jd_id`
2. Upload one or more resumes → receive `resume_id`s
3. Select unscored resumes in the UI, or `POST /analysis/fast-track` with JD + resume IDs → scores
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
- Deep analysis requires a running Celery worker, Celery beat, and Redis. Run exactly one beat scheduler. Committed pending analyses are dispatched every 30 seconds and retried after publication failures; duplicate deliveries are ignored by an atomic worker claim. No schema migration is required. Claimed jobs have a configurable `DEEP_ANALYSIS_TIMEOUT_SECONDS` budget (default 240 seconds). A periodic recovery task marks abandoned claims failed after that budget plus 60 seconds; users can explicitly retry. Late worker results cannot overwrite recovered failures.
- Alembic migrations need a live Postgres instance.

### Partial batch uploads

Batch upload commits each document independently. A parsing or persistence failure
removes that file and rolls back its record, while other files continue. The HTTP
200 response includes `resumes` for successes and `errors` with zero-based input
`index`, `filename`, and a safe error message for each failure. `total` counts all
submitted files; `succeeded + failed = total`. All-file failures also return these
per-file results. Injection warnings do not count as upload failures.

Both screens show failed filenames and messages. Successful files appear in
**Unscored resumes**, where they remain available even if the response is lost or
the page refreshes. Upload only failed files again when retrying a partial batch.
Request size/count validation still happens before any files are ingested.

### Upload resource limits

Oversized uploads return HTTP 413. Defaults: 10 MiB per file, 50 MiB total file
content per batch, and 20 files per batch. Request bodies are also capped while
streaming, with 1 MiB additional allowance for multipart metadata. Configure
`MAX_UPLOAD_FILE_BYTES`, `MAX_UPLOAD_BATCH_BYTES`, and `MAX_UPLOAD_FILES` to change
these limits. Docling accepts at most `MAX_DOCUMENT_PAGES` (default 50) and PDF/image
conversion uses `DOCUMENT_TIMEOUT_SECONDS` (default 120). Incomplete conversions
are rejected instead of scoring partial text.

## Authentication and organizations

The browser UI and `/api` must share one public origin. Local Vite already proxies
`/api` to FastAPI. All hiring endpoints, including resume downloads, require a
verified account with an active organization membership and completed sign-in.
Owners must enroll an authenticator app; MFA is optional for members. Both roles
can use all hiring features. Owners manage invitations and member removal.
Each account belongs to at most one organization.

Keep the encryption key you generated in [Quick start](#configure-env) outside
version control and back it up securely. It encrypts authenticator secrets and
queued email links. All API and worker processes must use the same keys.
Multiple keys are supported, newest first; retain older keys while stored secrets
still use them. Do not change keys without preserving decryptability.

Both [startup workflows](#quick-start) use the Mailpit inbox at
`http://localhost:8026`. Host processes use SMTP at `localhost:1026`, and
containers use `mailpit:1025`. Authentication email is committed to an
encrypted outbox, then delivered by Celery beat/worker every 15 seconds. Failed
SMTP deliveries retry with exponential delays, up to five attempts. After delivery,
expiry, or exhausting retries, the queued payload is erased. Users may request a
fresh verification/reset link; owners may reissue an invitation.

Signup sends a verification link. After verification, sign in, enroll an
authenticator, and save the ten recovery codes. Invite teammates from
**Organization**. Invited new users create a password and join that organization
without creating another workspace. Existing verified users without a membership
sign in before accepting. Invitations cannot move an account between organizations.
Removed members are signed out immediately; their account remains available for
a future invitation. Already committed analysis jobs continue for the organization.

MFA recovery requires an unused recovery code plus the account password. Password
reset does not remove MFA. **Losing the authenticator and every recovery code means
losing access. There is no emergency, email-only, or operator MFA reset.** Owners
cannot disable MFA or remove themselves. Organization switching, ownership transfer,
SSO, API bearer tokens, email changes, and account deletion are not implemented.

### Session API

Start browser or cookie-jar requests with `GET /api/v1/auth/session`. It issues an
HttpOnly session cookie and returns `state`, `csrf_token`, user, organization, and
MFA status. Send its CSRF token in `X-CSRF-Token` and the configured `PUBLIC_ORIGIN`
in `Origin` on every POST/DELETE, including login and multipart uploads. Session
rotation returns a new CSRF token; keep the cookie jar and returned token current.
No credentials or authentication tokens belong in local storage.

| Method | Path under `/api/v1` | Purpose |
|--------|----------------------|---------|
| GET | `/auth/session` | Bootstrap/inspect session and obtain CSRF token |
| POST | `/auth/register` | Email, password, organization name |
| POST | `/auth/verify-email`, `/auth/resend-verification` | Complete/request verification |
| POST | `/auth/login` | Start password sign-in; may require MFA/enrollment |
| POST | `/auth/logout`, `/auth/logout-all` | Revoke current/all sessions |
| POST | `/auth/forgot-password`, `/auth/reset-password` | Email recovery and token-based password change |
| POST | `/auth/change-password` | Current and new password; revoke other sessions |
| POST | `/auth/mfa/enroll`, `/auth/mfa/confirm` | Initial enrollment or replacement; show recovery codes once |
| POST | `/auth/mfa/challenge` | Complete sign-in with TOTP/recovery code |
| POST | `/auth/mfa/recovery-codes`, `/auth/mfa/disable` | Password + current second factor required |
| POST | `/auth/accept-invitation` | Consume invitation and join the organization |
| GET | `/organization`, `/organization/members` | Current workspace and members |
| GET/POST | `/organization/invitations` | Owner invitation management |
| DELETE | `/organization/invitations/{id}`, `/organization/members/{id}` | Owner revocation/removal |

Error responses keep the problem-response shape. Authentication error `title`
values are stable codes such as `session_expired`, `csrf_failed`, `invalid_factor`,
`owner_required`, and `rate_limited`. Rate limits return `Retry-After`.
Registration, verification resends, and password-recovery requests use the same
accepted message for existing and unknown accounts. No token is consumed by GET;
email links use URL fragments and confirmation pages strip the fragment immediately.

Session defaults are 30 minutes idle and 12 hours absolute; incomplete sessions
last 10 minutes. Verification links last 24 hours, reset links 30 minutes, and
invitations 72 hours. Passwords allow 15–128 characters, spaces, and Unicode.
Redis holds shared authentication counters. Authentication fails closed if Redis
is unavailable. Login/MFA allow five failures per account and thirty per IP in
five minutes; email-triggering operations allow three per email and twenty per IP
per hour. Anonymous session bootstrap is limited to sixty requests per IP/minute.
Existing general upload/request limits remain in force.

### Production configuration and migration

Set `ENVIRONMENT=production`, `PUBLIC_ORIGIN=https://your-host`, and
`AUTH_ALLOW_INSECURE_COOKIES=false`. Terminate HTTPS at your proxy and route `/api`
to FastAPI under the same origin. Preserve `Origin` headers. Configure the server
client IP through a trusted proxy only; do not trust arbitrary forwarded headers
for throttling. Serve `frontend/dist` with SPA fallback and do not expose the
upload directory. Sensitive API/file responses use `Cache-Control: no-store`.
Interactive API docs and the public OpenAPI schema are disabled in production.

Configure a real SMTP service using `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, `SMTP_FROM`, and `SMTP_STARTTLS=true` (STARTTLS submission).
Mailpit is only a development mail sink; replace the Compose SMTP host/port
overrides when deploying production workers. Require strong encryption keys,
PostgreSQL, Redis, one beat scheduler, and Celery workers. Configuration knobs and
defaults are listed in `.env.example`.

Back up the database and uploads before migrating. Stop API writes, workers, and
beat, run `uv run alembic upgrade head`, then deploy the API, UI, and workers
together. The migration preserves existing IDs, files, and analyses and assigns
all previous hiring records to a locked **Legacy organization**. Newly registered
accounts cannot claim it. Assign its owner once through an email-bound invitation:

```bash
uv run python -m app.commands.invite_legacy_owner --email owner@example.com
```

Use a new account or an existing verified account without a membership. The email
invitation verifies the new owner's inbox; owner access remains locked until MFA
is completed. The command refuses already assigned organizations and cannot reset
an existing owner's access. Failed/expired unaccepted invitations can be reissued.

Monitor HTTP authentication errors/429s, Redis availability, and worker email
failures. Email logs contain outbox IDs, attempt counts, and exception types,
never link payloads. Hourly cleanup removes expired sessions, action tokens, and
outbox rows. Back up uploads and the encryption keys with the database.

### Authentication checks

```bash
uv run pytest tests/unit
# TEST_DATABASE_URL must name a dedicated PostgreSQL database ending in _test:
TEST_DATABASE_URL=postgresql+asyncpg://.../talentmatch_auth_test uv run pytest tests/integration
uv run ruff check app tests
uv run mypy app
cd frontend
npm test
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The new authentication, isolation, outbox, and migration integration tests use
real PostgreSQL. The throttle integration test uses `REDIS_URL` with randomly
namespaced test keys and cleans up those keys. Browser tests intercept all API
requests and never contact the running application or send email.
