"""SQLAlchemy engine/session setup."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

_engine = None
_SessionLocal = None


def _make_engine(url: str):
    if url.startswith("sqlite"):
        from sqlalchemy import event
        from sqlalchemy.pool import StaticPool

        engine = create_engine(
            url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        return engine
    return create_engine(url, pool_pre_ping=True)


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine(settings.database_url)
    return _engine


def get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def init_db(url: str | None = None):
    """Create tables. Pass url to override (e.g. tests)."""
    global _engine, _SessionLocal
    target = url or settings.database_url
    _engine = _make_engine(target)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    local = get_session_local()
    session = local()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI dependency."""
    local = get_session_local()
    session = local()
    try:
        yield session
    finally:
        session.close()
