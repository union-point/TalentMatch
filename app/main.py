import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.application.services.auth_sessions import AuthError
from app.config import settings
from app.core.logging_config import setup_logging
from app.infrastructure.security.auth_services import get_auth_services
from app.presentation.api.auth_dependencies import get_principal
from app.presentation.api.errors import (
    auth_exception_handler,
    global_exception_handler,
    validation_exception_handler,
)
from app.presentation.api.middleware import (
    PrivateResponseMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    TimingMiddleware,
)
from app.presentation.api.routes.analysis import router as analysis_router
from app.presentation.api.routes.auth import router as auth_router
from app.presentation.api.routes.dashboard import router as dashboard_router
from app.presentation.api.routes.ingestion import router as ingestion_router
from app.presentation.api.routes.organizations import router as organization_router
from app.presentation.api.uploads import UploadLimitMiddleware

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    services = await asyncio.to_thread(get_auth_services)
    logger.info("TalentMatch API starting up")
    yield
    await services.throttle.redis.aclose()
    get_auth_services.cache_clear()
    logger.info("TalentMatch API shutting down")


app = FastAPI(
    title="TalentMatch API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
)

# Middleware added later wraps middleware added earlier.
app.add_middleware(UploadLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(PrivateResponseMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(TimingMiddleware)


app.add_exception_handler(AuthError, auth_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(ingestion_router, dependencies=[Depends(get_principal)])
app.include_router(analysis_router, dependencies=[Depends(get_principal)])
app.include_router(dashboard_router, dependencies=[Depends(get_principal)])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
