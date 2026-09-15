"""FastAPI dependencies for auth — get_current_user, optional, and ownership guard."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.tokens import decode_token
from app.db.models import User
from app.db.session import get_db

# No global rate-limit here; per-route slowapi limits apply.


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """Return User if valid access token, else None — never raises. For public explore."""
    token = _extract_bearer(authorization)
    if not token:
        return None
    try:
        payload = decode_token(token, expected_type="access")
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = db.get(User, user_id)
        if not user or not user.is_active:
            return None
        return user
    except Exception:
        return None


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Require valid access token — 401 if missing/invalid. Use for protected routes."""
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token, expected_type="access")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from e


def require_owner(resource_owner_id: str | None, current_user: User):
    """Call inside route after fetching resource — 403 if not owner."""
    if resource_owner_id is None:
        # Legacy row with no owner — allow current user to claim? For now deny and require migration
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Resource has no owner — contact support")
    if str(resource_owner_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this resource")
