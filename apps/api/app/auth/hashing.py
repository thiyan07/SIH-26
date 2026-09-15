"""Password hashing — bcrypt directly (avoid passlib 72-byte bug with bcrypt 4.x)."""
from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    # bcrypt has 72-byte limit — truncate as passlib would, but our passwords are short
    pw = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        pw = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except Exception:
        return False


def validate_password_strength(password: str, min_length: int = 8) -> str | None:
    """Return error string if invalid, else None. Simple but extensible."""
    if len(password) < min_length:
        return f"Password must be at least {min_length} characters"
    if password.strip() != password:
        return "Password must not start or end with spaces"
    # Require at least one letter and one digit for basic hygiene — not too strict for rural users
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return "Password must contain at least one letter and one digit"
    return None
