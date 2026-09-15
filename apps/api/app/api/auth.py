"""Auth routes — register, login, refresh, logout, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.service import authenticate_user, issue_tokens, refresh_tokens, register_user, revoke_refresh_token
from app.db.models import User
from app.db.session import get_db
from app.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=200)
    language: str = Field(default="en", pattern="^(en|ta|hi)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    language: str
    is_active: bool
    is_verified: bool

    class Config:
        from_attributes = True


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        language=user.language or "en",
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    user = register_user(db, email=body.email, password=body.password, display_name=body.display_name, language=body.language)
    db.commit()
    return _user_to_response(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, email=body.email, password=body.password, ip=request.client.host if request.client else None)
    tokens = issue_tokens(db, user, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
    db.commit()
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    tokens = refresh_tokens(db, refresh_token=body.refresh_token, ip=request.client.host if request.client else None)
    db.commit()
    return TokenResponse(**tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    # Revoke the refresh token — idempotent
    revoke_refresh_token(db, body.refresh_token)
    db.commit()
    return None


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return _user_to_response(current_user)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.auth.service import revoke_all_for_user

    revoke_all_for_user(db, current_user.id)
    db.commit()
    return None
