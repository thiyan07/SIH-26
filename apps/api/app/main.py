"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import ai, analysis, businesses, data_sources, financial, geo, locations, market, rag
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Hyper-local business intelligence & financial advisory for rural entrepreneurs.",
)

limiter = Limiter(key_func=get_remote_address)
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
app.include_router(analysis.router)
app.include_router(ai.router)
app.include_router(data_sources.router)
app.include_router(geo.router)
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
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
