"""Search & query schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    q: str = Field(default="", max_length=255)
    kinds: List[str] = Field(default=["drug", "product"])
    system_id: Optional[str] = None
    therapeutic_group_id: Optional[str] = None
    pharmacological_class_id: Optional[str] = None
    dosage_form: Optional[str] = None
    route: Optional[str] = None
    manufacturer_id: Optional[str] = None
    country_id: Optional[str] = None
    verification_status: Optional[str] = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchHitOut(BaseModel):
    kind: str
    id: str
    name_en: str
    name_ar: str = ""
    subtitle: str = ""
    match_type: str
    score: float
    verification_status: str
    is_demo: bool = False
    extra: Dict[str, Any] = {}


class SearchResponseOut(BaseModel):
    query: str
    total: int
    items: List[SearchHitOut]
    took_ms: int = 0
    suggestions: List[str] = []


class SuggestOut(BaseModel):
    suggestions: List[Dict[str, str]]


class BarcodeLookup(BaseModel):
    barcode: str = Field(..., min_length=4, max_length=64)
