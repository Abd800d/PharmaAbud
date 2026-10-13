"""FastAPI dependencies: current user, permissions, rate limiting (§28, §37)."""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.rate_limit import check_rate_limit
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(route_group: str = "default") -> Callable:
    def dependency(request: Request) -> None:
        check_rate_limit(client_key(request), route_group)

    return dependency


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError()
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except Exception:
        raise UnauthorizedError("Invalid or expired token.")
    user = db.get(User, payload.get("sub", ""))
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is inactive or missing.")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        return db.get(User, payload.get("sub", ""))
    except Exception:
        return None


def require_permission(code: str) -> Callable:
    """RBAC gate. Raises 403 when the user's roles lack `code`."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not user.has_permission(code):
            raise ForbiddenError(f"Missing permission: {code}")
        return user

    return dependency


def require_any_permission(*codes: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not any(user.has_permission(c) for c in codes):
            raise ForbiddenError(f"Missing permission: one of {', '.join(codes)}")
        return user

    return dependency
