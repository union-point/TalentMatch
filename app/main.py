import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging_config import setup_logging
from app.presentation.api.errors import global_exception_handler, validation_exception_handler
from app.presentation.api.middleware import (
    RateLimitMiddleware,
    RequestIDMiddleware,
    TimingMiddleware,
)
from app.presentation.api.routes.analysis import router as analysis_router
from app.presentation.api.routes.dashboard import router as dashboard_router
from app.presentation.api.routes.ingestion import router as ingestion_router

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("TalentMatch API starting up")
    yield
    logger.info("TalentMatch API shutting down")


app = FastAPI(
    title="TalentMatch API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(ingestion_router)
app.include_router(analysis_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
