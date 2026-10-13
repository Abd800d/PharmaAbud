"""Standard API error model.

Clients receive friendly codes/messages — never raw stack traces.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class AphError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": details or {}})


class NotFoundError(AphError):
    def __init__(self, entity: str, entity_id: str | None = None) -> None:
        message = f"{entity} was not found."
        super().__init__(status.HTTP_404_NOT_FOUND, "not_found", message, {"entity": entity, "id": entity_id})


class UnauthorizedError(AphError):
    def __init__(self, message: str = "Authentication is required.") -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


class ForbiddenError(AphError):
    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "forbidden", message)


class ValidationFailed(AphError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", message, details)


class ConflictError(AphError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "conflict", message, details)


class RateLimitError(AphError):
    def __init__(self) -> None:
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", "Too many requests. Please retry later.")
