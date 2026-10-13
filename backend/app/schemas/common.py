"""Common API schemas: pagination, messages, verification."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int = 0
    page: int = 1
    limit: int = 25
    has_more: bool = False
    next_cursor: Optional[str] = None


class Message(BaseModel):
    message: str
    code: str = "ok"


class VerificationTransition(BaseModel):
    new_status: str = Field(..., examples=["verified"])
    notes: str = ""


class VerificationRecordOut(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    previous_status: str
    new_status: str
    version: int
    reviewer_id: Optional[str] = None
    review_date: Optional[datetime] = None
    notes: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    previous_value: str = ""
    new_value: str = ""
    timestamp: datetime
    ip_address: str = ""

    model_config = {"from_attributes": True}
