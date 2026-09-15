"""Auth service — register, login, refresh, logout with lockout and session tracking."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.hashing import hash_password, validate_password_strength, verify_password
from app.auth.tokens import create_access_token, create_refresh_token, decode_token, hash_token
from app.config import settings
from app.db.models import User, UserSession


def _now():
    return datetime.now(timezone.utc)


def register_user(db: Session, email: str, password: str, display_name: str | None = None, language: str = "en") -> User:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
    existing = db.execute(select(User).where(User.email == email)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    err = validate_password_strength(password, settings.password_min_length)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        language=language or "en",
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, email: str, password: str, ip: str | None = None) -> User:
    email = email.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalars().first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    # Lockout check
    if user.lockout_until and user.lockout_until > _now():
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account temporarily locked. Try again later.")
    if not verify_password(password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= settings.auth_lockout_attempts:
            user.lockout_until = _now() + timedelta(minutes=settings.auth_lockout_minutes)
        db.flush()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    # Success — reset lockout, update last_login
    user.failed_login_attempts = 0
    user.lockout_until = None
    user.last_login = _now()
    db.flush()
    return user


def issue_tokens(db: Session, user: User, ip: str | None = None, user_agent: str | None = None) -> dict:
    access_token, access_jti, access_exp = create_access_token(user.id, user.email or "")
    refresh_token, refresh_jti, refresh_hash, refresh_exp = create_refresh_token(user.id)
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=refresh_exp,
        ip_address=ip,
        user_agent=user_agent,
        is_revoked=False,
    )
    db.add(session)
    db.flush()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": int((access_exp - _now()).total_seconds()),
        "refresh_expires_in": int((refresh_exp - _now()).total_seconds()),
        "access_jti": access_jti,
        "refresh_jti": refresh_jti,
    }


def refresh_tokens(db: Session, refresh_token: str, ip: str | None = None) -> dict:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
        token_hash = hash_token(refresh_token)
        session = db.execute(select(UserSession).where(UserSession.refresh_token_hash == token_hash)).scalars().first()
        if not session or session.is_revoked or session.expires_at < _now():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or revoked")
        user = db.get(User, session.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")
        # Rotate — revoke old, issue new pair
        session.is_revoked = True
        db.flush()
        return issue_tokens(db, user, ip=ip)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from e


def revoke_refresh_token(db: Session, refresh_token: str):
    token_hash = hash_token(refresh_token)
    session = db.execute(select(UserSession).where(UserSession.refresh_token_hash == token_hash)).scalars().first()
    if session:
        session.is_revoked = True
        db.flush()


def revoke_all_for_user(db: Session, user_id: str):
    sessions = db.execute(select(UserSession).where(UserSession.user_id == user_id, UserSession.is_revoked == False)).scalars().all()  # noqa: E712
    for s in sessions:
        s.is_revoked = True
    db.flush()
