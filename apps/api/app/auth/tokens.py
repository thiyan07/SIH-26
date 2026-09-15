"""JWT helpers — access + refresh, with jti for revocation."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, email: str) -> tuple[str, str, datetime]:
    """Return (token, jti, expires_at). Short-lived."""
    jti = str(uuid.uuid4())
    exp = _now() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "email": email,
        "jti": jti,
        "type": "access",
        "exp": exp,
        "iat": _now(),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, exp


def create_refresh_token(user_id: str) -> tuple[str, str, str, datetime]:
    """Return (token, jti, token_hash(sha256), expires_at). Long-lived, stored hashed."""
    jti = str(uuid.uuid4())
    exp = _now() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {"sub": user_id, "jti": jti, "type": "refresh", "exp": exp, "iat": _now()}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    # Hash for DB storage — never store raw refresh token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, jti, token_hash, exp


def decode_token(token: str, expected_type: str | None = None) -> dict:
    """Decode and verify signature/exp. Raises jwt exceptions on failure."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected {expected_type} token, got {payload.get('type')}")
    return payload


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
