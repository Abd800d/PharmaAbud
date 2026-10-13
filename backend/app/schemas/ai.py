"""AI assistant schemas (§41–§43)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AiAskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    language: str = Field(default="en", pattern="^(en|ar)$")
    conversation_id: Optional[str] = None
    device_id: str = ""


class AiCitationOut(BaseModel):
    source_id: str = ""
    source_name: str = ""
    source_url: str = ""
    section: str = ""
    entity_type: str = ""
    entity_id: str = ""
    last_verified_date: str = ""


class AiAskResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: List[AiCitationOut] = []
    disclaimer: str
    provider: str
    intent: str = ""
    retrieved_entities: List[str] = []
    grounded: bool = False
