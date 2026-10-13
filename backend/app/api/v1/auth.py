"""Authentication endpoints (§45): register, login, refresh, password reset."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, rate_limit
from app.core.errors import UnauthorizedError, ValidationFailed
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.db.session import get_db
from app.models import Role, User, utcnow
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        preferred_language=user.preferred_language,
        roles=[{"id": r.id, "code": r.code, "name_en": r.name_en, "name_ar": r.name_ar} for r in user.roles],
        permissions=sorted(user.permission_codes),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/register", response_model=UserOut, dependencies=[Depends(rate_limit("auth"))])
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> UserOut:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise ValidationFailed("An account with this email already exists.")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        preferred_language=payload.preferred_language,
    )
    # default role: public_user
    role = db.scalar(select(Role).where(Role.code == "public_user"))
    if role:
        user.roles.append(role)
    db.add(user)
    db.flush()
    record_audit(db, action="user.registered", entity_type="user", entity_id=user.id,
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return _user_out(user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit("auth"))])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        if user is not None:
            user.failed_login_count = (user.failed_login_count or 0) + 1
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled.")
    user.failed_login_count = 0
    user.last_login_at = utcnow()
    settings = get_settings()
    record_audit(db, action="user.login", entity_type="user", entity_id=user.id,
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return TokenResponse(
        access_token=create_access_token(user.id, {"roles": [r.code for r in user.roles]}),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(rate_limit("auth"))])
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token = decode_token(payload.refresh_token, expected_type="refresh")
    except Exception:
        raise UnauthorizedError("Invalid refresh token.")
    user = db.get(User, token.get("sub", ""))
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is inactive or missing.")
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user.id, {"roles": [r.code for r in user.roles]}),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.post("/password-reset/request", dependencies=[Depends(rate_limit("auth"))])
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    # never reveal whether the account exists
    if user is not None:
        raw, hashed = generate_password_reset_token()
        user.password_reset_token = hashed
        from datetime import datetime, timedelta

        settings = get_settings()
        user.password_reset_expires = datetime.utcnow() + timedelta(minutes=settings.password_reset_expire_minutes)
        db.flush()
        # In production, email the raw token via a transactional mail service.
        # The raw token is intentionally NOT returned by the API.
    return {"message": "If the account exists, a password reset link has been sent."}


@router.post("/password-reset/confirm", dependencies=[Depends(rate_limit("auth"))])
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> dict:
    hashed = hash_reset_token(payload.token)
    user = db.scalar(select(User).where(User.password_reset_token == hashed))
    if user is None or user.password_reset_expires is None or user.password_reset_expires < utcnow():
        raise ValidationFailed("Reset token is invalid or expired.")
    user.password_hash = hash_password(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.flush()
    return {"message": "Password updated."}
