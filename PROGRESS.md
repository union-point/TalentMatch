# Progress

## Completed

### Milestone 1 — Foundation

- [x] `pyproject.toml` with all dependencies (fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, python-multipart, celery[redis], google-genai, docling, pytest, pytest-asyncio, httpx, ruff, mypy)
- [x] `app/__init__.py` — package marker
- [x] `app/main.py` — FastAPI app factory with CORS, lifespan, health endpoint
- [x] `app/config.py` — `Settings` class via `pydantic-settings` (DATABASE_URL, GEMINI_API_KEY, REDIS_URL, UPLOAD_DIR, CORS_ORIGINS, LOG_LEVEL)
- [x] `app/infrastructure/persistence/database.py` — Async engine, `async_session` factory, `get_db` dependency
- [x] `app/infrastructure/persistence/models/base.py` — SQLAlchemy declarative base + `UUIDMixin` (id, created_at, updated_at)
- [x] `alembic.ini` + `alembic/env.py` — Alembic configured for async
- [x] `alembic/versions/001_initial_empty.py` — Empty initial migration
- [x] `docker-compose.yml` — PostgreSQL 16, Redis 7, app service
- [x] `Dockerfile` — Multi-stage build (builder + runtime), non-root user, HEALTHCHECK, uv-installed
- [x] `Makefile` — `make dev`, `make migrate`, `make test`
- [x] `.env.example` — All required env vars
- [x] All package `__init__.py` files and directory stubs
- [x] All test `__init__.py` files and directory stubs
- [x] `GET /health` returns `{"status": "ok"}` — verified
- [x] `ruff check` passes clean
- [x] `mypy` passes with no issues
- [x] `pytest` runs (empty suite)

### Milestone 2 — Domain Entities + Persistence

- [x] `app/domain/value_objects.py` — `Score`, `AnalysisStatus` (Enum), `InjectionScanResult` (dataclass)
- [x] `app/domain/entities/job_description.py` — `JobDescription` entity
- [x] `app/domain/entities/resume.py` — `Resume` entity
- [x] `app/domain/entities/fast_track_result.py` — `FastTrackResult` entity
- [x] `app/domain/entities/deep_analysis.py` — `DeepAnalysis` entity
- [x] `app/domain/ports/repository.py` — Abstract repository ports
- [x] `app/infrastructure/persistence/models/job_description.py` — ORM model
- [x] `app/infrastructure/persistence/models/resume.py` — ORM model
- [x] `app/infrastructure/persistence/models/fast_track_result.py` — ORM model
- [x] `app/infrastructure/persistence/models/deep_analysis.py` — ORM model
- [x] `app/infrastructure/persistence/repositories/job_description_repo.py` — SQLAlchemy impl
- [x] `app/infrastructure/persistence/repositories/resume_repo.py` — SQLAlchemy impl
- [x] `app/infrastructure/persistence/repositories/fast_track_repo.py` — SQLAlchemy impl
- [x] `app/infrastructure/persistence/repositories/deep_analysis_repo.py` — SQLAlchemy impl
- [x] `alembic/versions/002_create_tables.py` — Full schema migration
- [x] `ruff check` passes clean
- [x] `mypy` passes with no issues
- [x] 22 unit tests for domain entities + value objects pass

### Milestone 3 — File Ingestion Pipeline

- [x] `app/domain/ports/file_parser.py` — Abstract `FileParser` port
- [x] `app/domain/ports/file_storage.py` — Abstract `FileStorage` port
- [x] `app/core/exceptions.py` — Custom exceptions (UnsupportedFileTypeError, ParsingError, etc.)
- [x] `app/infrastructure/parsing/docling_parser.py` — Docling-based parser with OCR + table extraction
- [x] `app/infrastructure/parsing/parser_factory.py` — File extension → Docling dispatch
- [x] `app/infrastructure/parsing/text_normalizer.py` — Unicode normalization, whitespace collapse
- [x] `app/infrastructure/security/prompt_injection_detector.py` — Injection detection (invisible chars, suspicious patterns, hidden content)
- [x] `app/infrastructure/storage/local_file_storage.py` — Local filesystem storage with UUID names
- [x] `app/application/dto/ingestion.py` — `IngestionResponse` DTO
- [x] `app/application/services/ingestion_service.py` — Orchestration: save → parse → normalize → scan → persist
- [x] `app/presentation/schemas/job_description.py` — Pydantic response schemas
- [x] `app/presentation/schemas/resume.py` — Pydantic response schemas
- [x] `app/presentation/api/routes/ingestion.py` — Upload endpoints (JD, resume, batch)
- [x] `app/presentation/api/dependencies.py` — FastAPI dependency injection wiring
- [x] `app/main.py` — Router registration
- [x] `ruff check` passes clean
- [x] `mypy` passes with no issues
- [x] 73 tests pass (22 domain + 44 unit infrastructure + 7 integration)

### Milestone 4 — Gemini AI Integration

- [x] `app/core/exceptions.py` — Added `AIResponseError` exception
- [x] `app/domain/ports/ai_service.py` — Abstract `AIService` port with `analyze_fast_track` and `analyze_deep`
- [x] `app/application/dto/analysis.py` — `FastTrackResultData`, `DeepAnalysisData`, `EvidenceItem` (Pydantic models)
- [x] `app/infrastructure/ai/prompts.py` — System prompts (expert HR recruiter persona) and user prompt builders
- [x] `app/infrastructure/ai/gemini_service.py` — Gemini implementation:
  - Structured JSON output via `response_schema` + `response_mime_type="application/json"`
  - `asyncio.to_thread()` for non-blocking sync SDK calls
  - Exponential backoff retry (3 attempts) for timeouts, rate limits, and 5xx errors
  - Non-retryable 4xx errors raised immediately
  - Token usage logging via `response.usage_metadata`
  - Timeout: 30s fast-track, 60s deep
  - `AIResponseError` on empty/malformed responses
- [x] `ruff check` passes clean
- [x] `mypy` passes with no issues
- [x] 15 unit tests for AI service (fast-track, deep analysis, error handling, retry logic, logging, port contract)

### Milestone 5 — Fast-Track Analysis

- [x] `app/application/services/fast_track_service.py` — Batch orchestration with `asyncio.gather` + semaphore (max 5 concurrent Gemini calls); partial failure handling; injection-flagged resume warning
- [x] `app/presentation/schemas/analysis.py` — `FastTrackRequest`, `FastTrackResultSchema`, `FastTrackResponse` Pydantic schemas
- [x] `app/presentation/api/routes/analysis.py` — `POST /api/v1/analysis/fast-track` endpoint; 404 on missing JD; per-resume error entries
- [x] `app/presentation/api/dependencies.py` — `get_fast_track_service` dependency added (wires repos + GeminiService)
- [x] `app/main.py` — Analysis router registered
- [x] `ruff check` passes clean
- [x] `mypy` passes with no issues
- [x] 88 tests pass (all prior tests green)

### Milestone 6 — Deep Analysis

- [x] `app/core/exceptions.py` — Added `AnalysisNotFoundError`
- [x] `app/application/services/deep_analysis_service.py` — Service with `request_deep_analysis()` (creates pending record + dispatches Celery task) and `get_result()` (returns status/results)
- [x] `app/tasks/celery_app.py` — Celery app configured from `app.config` (Redis broker)
- [x] `app/tasks/deep_analysis_tasks.py` — Celery task: update status → call Gemini → persist result → mark completed/failed; uses `asyncio.run()` for async AI call
- [x] `app/presentation/schemas/analysis.py` — Added `DeepAnalysisRequest`, `DeepAnalysisResponse`, `DeepAnalysisResultSchema`, `EvidenceSchema`
- [x] `app/presentation/api/routes/analysis.py` — `POST /api/v1/analysis/deep` (202 Accepted) and `GET /api/v1/analysis/deep/{analysis_id}`
- [x] `app/presentation/api/dependencies.py` — `get_deep_analysis_service` dependency wired
- [x] `ruff check` passes clean (only pre-existing alembic long-line warnings)
- [x] `mypy` passes with no issues
- [x] All 88 existing tests remain green


### Milestone 4 extension  — AI Provider Factory

- [x] `app/config.py` — Added `AI_FAST_TRACK_PROVIDER`, `AI_FAST_TRACK_MODEL`, `AI_DEEP_ANALYSIS_PROVIDER`, `AI_DEEP_ANALYSIS_MODEL` settings
- [x] `app/infrastructure/ai/ai_factory.py` — `AIServiceFactory` with registry pattern; `create(provider, model)` internally resolves provider-specific kwargs (`api_key`, `base_url`) from `settings`
- [x] `app/infrastructure/ai/__init__.py` — Default provider registration (`GeminiService` for both tasks)
- [x] `app/infrastructure/ai/gemini_service.py` — `model` parameter added to `__init__`; hardcoded `GEMINI_MODEL` removed
- [x] `app/presentation/api/dependencies.py` — Fast-Track DI uses `AIServiceFactory.create(provider=..., model=...)` — `_ai_kwargs()` helper removed, no provider-specific args leaked to this layer
- [x] `app/tasks/deep_analysis_tasks.py` — Celery task uses `AIServiceFactory.create(provider=..., model=...)` — `_ai_kwargs()` helper removed
- [x] `ruff check` passes clean
- [x] Adding `GroqService` later only requires implementing `AIService` and calling `AIServiceFactory.register(...)`

### OpenAI Provider (extension)

- [x] `pyproject.toml` — Added `openai>=1.0.0` dependency
- [x] `app/config.py` — Added `OPENAI_API_KEY` (default `""`) and `OPENAI_BASE_URL` (default OpenAI v1) settings
- [x] `app/infrastructure/ai/openai_service.py` — `OpenAIService` implementing `AIService`:
  - Configurable `model`, `api_key`, `base_url` constructor params
  - `ResponseFormatJSONSchema` structured output (falls back to `json_object` for providers that don't support it)
  - `model_validate_json` Pydantic parsing — same contract as `GeminiService`
  - Exponential backoff retry (3 attempts); non-retryable 4xx raised immediately
  - Token usage logging via `response.usage`
  - Semaphore limiting concurrent requests (max 2)
- [x] `app/infrastructure/ai/__init__.py` — Registers `OpenAIService` under `"openai"` key
- [x] `app/presentation/api/dependencies.py` — Calls `AIServiceFactory.create(provider=..., model=...)`; kwargs resolved in factory, not in DI layer
- [x] `app/tasks/deep_analysis_tasks.py` — Same simplified `AIServiceFactory.create(provider=..., model=...)` call
- [x] Switch provider via `.env`: `AI_FAST_TRACK_PROVIDER=openai`, `AI_FAST_TRACK_MODEL=gpt-4o-mini`, `OPENAI_API_KEY=sk-...`
- [x] `ruff check` passes clean; `mypy` clean on all new/modified files


### Deep Analysis Test Suite (33 tests)

- [x] `tests/unit/application/test_deep_analysis_service.py` — 11 unit tests for `DeepAnalysisService`:
  - `request_deep_analysis`: happy path, JD not found, resume not found, no save on missing JD, no task dispatch on missing resume
  - `get_result`: completed analysis, pending, in-progress, failed with error, not found, repo delegation
- [x] `tests/unit/infrastructure/test_deep_analysis_tasks.py` — 8 unit tests for Celery task `_run_deep_analysis_async`:
  - Happy path (full lifecycle: pending → in_progress → completed)
  - Analysis not found aborts
  - Resume/JD not found marks FAILED
  - AI exception marks FAILED with error message
  - Status transitions (pending → in_progress → completed)
  - Factory called with correct settings
  - AI receives normalized content
- [x] `tests/integration/test_analysis.py` — 14 API contract tests for deep analysis routes:
  - `POST /api/v1/analysis/deep`: 202, 404 (JD/resume), 422 (invalid body/UUID), correct service args
  - `GET /api/v1/analysis/deep/{id}`: completed, pending, in-progress, failed, 404, 422, correct args, empty evidence
- [x] `ruff check` passes clean
- [x] `mypy` passes with no issues
- [x] All 114 tests pass (81 existing + 33 new)


### Milestone 7 — Dashboard + Candidate Ranking

- [x] `app/domain/ports/repository.py` — Added `FastTrackRepository.get_by_job_description_id()` and `DeepAnalysisRepository.get_by_resume_and_jd()` abstract methods
- [x] `app/infrastructure/persistence/repositories/fast_track_repo.py` — Implemented `get_by_job_description_id()` with score-descending order
- [x] `app/infrastructure/persistence/repositories/deep_analysis_repo.py` — Implemented `get_by_resume_and_jd()` for resume+JD lookup
- [x] `app/application/services/dashboard_service.py` — Service with `get_ranked_candidates()`, `get_candidate_detail()`, `get_resume_file()`:
  - Ranked candidates: min_score, pass_fail_only, search (by name), pagination
  - Candidate detail: resume info + fast_track + deep_analysis (all nullable)
  - Resume file download: MIME type mapping, file existence check
- [x] `app/presentation/schemas/dashboard.py` — `RankedCandidateSchema`, `CandidateDetailSchema`, `PaginatedResponse`, `FastTrackSummarySchema`, `DeepAnalysisSummarySchema`
- [x] `app/presentation/api/routes/dashboard.py` — Three endpoints:
  - `GET /api/v1/dashboard/jobs/{jd_id}/candidates` — ranked list with filters
  - `GET /api/v1/dashboard/candidates/{resume_id}/job/{jd_id}` — candidate detail
  - `GET /api/v1/dashboard/candidates/{resume_id}/resume-file` — file download
- [x] `app/presentation/api/dependencies.py` — Added `get_dashboard_service` dependency wiring
- [x] `app/main.py` — Registered dashboard router
- [x] `ruff check` passes clean
- [x] `mypy` passes with no issues
- [x] 15 unit tests for `DashboardService` (ranking, filtering, pagination, detail, file download, error cases)
- [x] 14 integration tests for dashboard API routes (200, 404, 422, query params, service arg verification)
- [x] All 143 tests pass (114 pre-existing + 29 new)

### Milestone 9 — Security Hardening + Production Polish

- [x] `app/domain/value_objects.py` — `InjectionScanResult` enhanced with `suspicion_score: int` field
- [x] `app/infrastructure/security/prompt_injection_detector.py` — Major rewrite:
  - Full Unicode category scan (Cf, Cc, Mn, Zl, Zp) for invisible character detection
  - Entropy-based anomaly detection (Shannon entropy threshold > 6.0 for text > 100 chars)
  - Configurable 0-100 suspicion scoring with `PASS_THRESHOLD = 15`
  - Expanded known injection phrase library (25 patterns including jailbreak, DAN, reveal prompt, bypass safeguards, etc.)
  - Hidden content analysis expanded (opacity:0, off-screen positioning, negative z-index)
  - `_scan_invisible_characters()`, `_find_known_injection_phrases()`, `_scan_hidden_content()`, `_compute_entropy()` sub-functions
- [x] `app/presentation/schemas/job_description.py` — `InjectionScanDetails` includes `suspicion_score`
- [x] `app/presentation/api/errors.py` — RFC 7807 problem+json global exception handlers:
  - `global_exception_handler` — Maps each `AppError` subclass to proper HTTP status with `trace_id`
  - `validation_exception_handler` — Catches `RequestValidationError` with structured 422 response
  - Error details include `type`, `title`, `status`, `detail`, `trace_id`, optional `extra`
- [x] `app/core/logging_config.py` — Structured JSON logging with:
  - `StructuredJSONFormatter` producing JSON log entries with timestamp, level, logger, message, request_id, exception
  - `request_id_var` context variable for per-request ID propagation
  - `setup_logging()` configured from `settings.log_level`
- [x] `app/presentation/api/dependencies.py` — Three middleware classes:
  - `RequestIDMiddleware` — Generates UUID per request, sets `request_id_var`, adds `X-Request-ID` response header
  - `TimingMiddleware` — Measures request duration, adds `X-Response-Time-Ms` response header
  - `RateLimitMiddleware` — In-memory sliding window (100 requests per 60s per IP); returns RFC 7807 429 response
- [x] `app/main.py` — Lifespan logging, middleware stack (CORS → RequestID → Timing → RateLimit), exception handlers registered
- [x] `ruff check` passes clean
- [x] 117 unit tests pass (all prior + 4 new injection detector tests)

### AIService Factory Singleton Cache

- [x] `app/infrastructure/ai/ai_factory.py` — `AIServiceFactory.create()` memoized: same `(provider, model)` tuple returns the cached `AIService` instance; different combinations get separate instances
- [x] ruff check passes clean
- [x] mypy passes with no issues
- [x] 117 unit tests pass (no regressions)

## Current State

Milestone 9 — Security Hardening + Production Polish (ongoing)

### Prompt Injection Pipeline Fix

- Fixed `BatchUploadResponse` `succeeded`/`failed` fields: `succeeded` now counts ALL uploaded resumes (not just injection-passing), `failed` is always 0 (uploads never fail due to injection)
- Fixed frontend "Run Analysis" button: now appears when `uploadResult.total > 0` instead of `uploadResult.succeeded > 0`, so injection-flagged resumes don't hide the button
- Fixed integration test: assertion for injection scan details key corrected from `suspicious_instructions` to `known_injection_phrases`
- Prompt injection detector no longer blocks or drops processing — it only marks/informs
- Both single upload and batch processing work correctly with injection-flagged resumes

### Injection Detector False-Positive Reduction

- Unicode NFC normalization at scan start prevents accented names (NFD) from being flagged
- Mn (combining marks) only flagged on runs of 3+ consecutive marks, not individual marks
- Cf (format chars) allowlisted for legitimate bidi marks (RLM, LRM, ALM, ZWJ, ZWNJ)
- Removed `system\s*:\s*` phrase pattern — eliminated false matches on "Operating System: Linux"
- Security keywords ("jailbreak", "bypass", "override") removed from standalone phrase library; detected only with imperative framing context
- Script-aware entropy thresholds (CJK: 9.5, Arabic/Hebrew: 7.5, Latin: 7.0)
- Corroboration rule: weak signals require 2+ categories to fail; strong signals (hidden content, injection phrases, invisible chars) can fail alone
- PASS_THRESHOLD renamed to FAIL_THRESHOLD_SCORE with clear scoring-direction comment
- PII-safe logging: WARNING level logs category labels only, not raw matched text
- 28 unit tests (14 original + 14 new), inline sanity check block


## Notes

- Alembic requires a running PostgreSQL instance for online migrations (`alembic upgrade head`).
- Docling downloads model artifacts on first run (cold-start latency).
- Gemini API key must be set in `.env` (`GEMINI_API_KEY`) for real API calls.
- The `google-genai` SDK 2.x uses a synchronous client; API calls are offloaded to a thread pool via `asyncio.to_thread()`.
