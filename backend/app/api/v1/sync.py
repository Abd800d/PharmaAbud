"""Sync endpoints (§30–§33)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_optional_user
from app.core.errors import ValidationFailed
from app.db.session import get_db
from app.models import DeviceSyncState, User
from app.schemas.sync import (
    SyncPullRequest,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncStatusOut,
)
from app.services.sync import pull_changes, push_changes

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/pull", response_model=SyncPullResponse)
def sync_pull(payload: SyncPullRequest, db: Session = Depends(get_db),
              user: User | None = Depends(get_optional_user)) -> SyncPullResponse:
    since = None
    if payload.since:
        try:
            since = datetime.fromisoformat(payload.since)
        except ValueError:
            raise ValidationFailed("'since' must be an ISO-8601 datetime.")
    page = pull_changes(
        db,
        user_id=user.id if user else None,
        device_id=payload.device_id,
        entity_type=payload.entity_type,
        since=since,
        system_ids=payload.system_ids or None,
        limit=payload.limit,
    )
    return SyncPullResponse(
        entity_type=page.entity_type,
        items=page.items,
        has_more=page.has_more,
        server_version=page.server_version,
        deleted_ids=page.deleted_ids,
        server_time=datetime.utcnow().isoformat(),
    )


@router.post("/push", response_model=SyncPushResponse)
def sync_push(payload: SyncPushRequest, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> SyncPushResponse:
    result = push_changes(
        db,
        user_id=user.id,
        device_id=payload.device_id,
        changes=[c.model_dump() for c in payload.changes],
    )
    return SyncPushResponse(**result)


@router.get("/status", response_model=list[SyncStatusOut])
def sync_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[SyncStatusOut]:
    rows = db.scalars(select(DeviceSyncState).where(DeviceSyncState.user_id == user.id)).all()
    import json

    out = []
    for s in rows:
        try:
            systems = json.loads(s.downloaded_systems or "[]")
        except Exception:
            systems = []
        out.append(SyncStatusOut(
            device_id=s.device_id,
            last_synced_at=s.last_synced_at.isoformat() if s.last_synced_at else None,
            status=s.status,
            dataset_mode=s.dataset_mode,
            downloaded_systems=systems,
            last_error=s.last_error,
        ))
    return out
