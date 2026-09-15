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
    auth,
    business_profiles,
    business_setup,
    businesses,
    data_sources,
    documents,
    financial,
    forecasts,
    gaps,
    geo,
    geocoder,
    loans,
    locations,
    market,
    monitoring,
    preloan_reports,
    rag,
    scenarios,
    suppliers,
    user_businesses,
)
from app.config import settings
from app.limiter import limiter

logger = logging.getLogger("grambiz.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure production DB has district_normalized column (for Render free tier where migration may not have run)
    try:
        from sqlalchemy import text as _text
        from app.db.session import session_scope
        from app.db.models import Base
        from app.db.session import get_engine

        # Create any new tables (UserSession, PreLoanReport) idempotently
        try:
            Base.metadata.create_all(get_engine())
        except Exception as e:
            logger.warning(f"create_all for new tables failed: {e}")
        with session_scope() as s:
            s.execute(_text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS district_normalized VARCHAR(100)"))
            s.execute(_text("CREATE INDEX IF NOT EXISTS ix_locations_district_normalized ON locations (district_normalized)"))
            # Phase 1 auth + tenant columns — idempotent
            s.execute(_text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)"))
            s.execute(_text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true"))
            s.execute(_text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT false"))
            s.execute(_text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ"))
            s.execute(_text("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0"))
            s.execute(_text("ALTER TABLE users ADD COLUMN IF NOT EXISTS lockout_until TIMESTAMPTZ"))
            s.execute(_text("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36)"))
            s.execute(_text("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS is_user_business BOOLEAN DEFAULT false"))
            s.execute(_text("CREATE INDEX IF NOT EXISTS ix_businesses_owner ON businesses (owner_id)"))
            s.execute(_text("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS user_id VARCHAR(36)"))
            s.execute(_text("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS engine_versions JSONB"))
            s.execute(_text("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS is_saved BOOLEAN DEFAULT false"))
            s.execute(_text("CREATE INDEX IF NOT EXISTS ix_analysis_runs_user_id ON analysis_runs (user_id)"))
            s.commit()
    except Exception as e:
        logger.warning(f"Startup migration for district_normalized / auth failed (may already exist): {e}")
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
    description="Enterprise business intelligence & financial advisory for small businesses and growing enterprises.",
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
app.include_router(auth.router)
app.include_router(user_businesses.router)
app.include_router(preloan_reports.router)
app.include_router(business_profiles.router)
app.include_router(loans.router)
app.include_router(monitoring.router)
app.include_router(gaps.router)
app.include_router(forecasts.router)
app.include_router(scenarios.router)
app.include_router(documents.router)
app.include_router(business_setup.router)
app.include_router(ai.router)
app.include_router(data_sources.router)
app.include_router(geo.router)
app.include_router(geocoder.router)
app.include_router(rag.router)
app.include_router(suppliers.router)


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
