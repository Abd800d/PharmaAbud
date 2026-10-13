"""Sync schemas (§32–§33)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SyncPullRequest(BaseModel):
    device_id: str = Field(..., min_length=4, max_length=64)
    entity_type: str = Field(default="drug", pattern="^(drug|product)$")
    since: Optional[str] = None  # ISO datetime watermark
    system_ids: List[str] = Field(default_factory=list)
    limit: int = Field(default=200, ge=1, le=1000)


class SyncPullResponse(BaseModel):
    entity_type: str
    items: List[Dict[str, Any]]
    has_more: bool
    server_version: int
    deleted_ids: List[str]
    server_time: str


class SyncChange(BaseModel):
    entity_type: str
    entity_id: str = ""
    operation: str = "update"
    payload: Dict[str, Any] = Field(default_factory=dict)
    local_version: int = 0
    base_version: int = 0


class SyncPushRequest(BaseModel):
    device_id: str = Field(..., min_length=4, max_length=64)
    changes: List[SyncChange] = Field(default_factory=list)


class SyncPushResponse(BaseModel):
    accepted: int
    conflicts: int
    failed: int
    results: List[Dict[str, Any]]
    server_time: str


class SyncStatusOut(BaseModel):
    device_id: str
    last_synced_at: Optional[str] = None
    status: str
    dataset_mode: str = "essential"
    downloaded_systems: List[str] = []
    last_error: str = ""
