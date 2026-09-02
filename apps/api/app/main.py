"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import (
    advisory,
    ai,
    analysis,
    businesses,
    data_sources,
    financial,
    geo,
    geocoder,
    locations,
    market,
    rag,
)
from app.config import settings
from app.limiter import limiter

logger = logging.getLogger("grambiz.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup hooks can be added here (e.g. verifying DB connectivity, cache
    # warm-up). For now startup is a no-op beyond FastAPI's defaults.
    logger.info("GramBiz API startup complete (env=%s)", settings.app_env)
    yield
    # Graceful shutdown: flush loggers and release resources.
    logger.info("GramBiz API shutting down gracefully")
    for handler in logger.handlers:
        handler.flush()


# Interactive docs stay local-only; the API surface is unauthenticated, so
# schema introspection is disabled outside development (Phase 28 hardening).
_expose_docs = settings.app_env == "development"

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Hyper-local business intelligence & financial advisory for rural entrepreneurs.",
    docs_url="/docs" if _expose_docs else None,
    redoc_url="/redoc" if _expose_docs else None,
    openapi_url="/openapi.json" if _expose_docs else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(locations.router)
app.include_router(businesses.router)
app.include_router(market.router)
app.include_router(financial.router)
app.include_router(advisory.router)
app.include_router(analysis.router)
app.include_router(ai.router)
app.include_router(data_sources.router)
app.include_router(geo.router)
app.include_router(geocoder.router)
app.include_router(rag.router)


@app.get("/")
@limiter.limit("60/minute")
def root(request: Request):
    return {
        "name": settings.app_name,
        "message": "Know Your Market Before You Take the Loan.",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Log the full stack trace server-side (S8) while returning only a generic
    # message to the client. Never leaks internal details.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
