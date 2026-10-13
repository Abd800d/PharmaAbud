"""Synchronization engine (§30–§33).

Flutter ⇄ Sync Engine ⇄ API ⇄ PostgreSQL.

- Incremental pull by watermark (updated_at + record_version)
- Push of local changes into the server sync_queue with conflict detection
- Never blindly overwrites newer server data (§32): if the server record
  changed after the client's base_version, the item is marked CONFLICT and
  returned for client-side resolution.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DeviceSyncState,
    Drug,
    Favorite,
    Product,
    SyncOperation,
    SyncQueueItem,
    SyncStatus,
    utcnow,
)

PAGE_SIZE = 200

_SYNCABLE = {"drug": Drug, "product": Product}


@dataclass
class PullPage:
    entity_type: str
    items: List[Dict[str, Any]]
    has_more: bool
    server_version: int
    deleted_ids: List[str]


def _drug_dict(d: Drug) -> Dict[str, Any]:
    return {
        "id": d.id,
        "generic_name_en": d.generic_name_en,
        "generic_name_ar": d.generic_name_ar,
        "scientific_name": d.scientific_name,
        "drug_class": d.drug_class,
        "pharmacological_class_name": d.pharmacological_class_name,
        "therapeutic_class_name": d.therapeutic_class_name,
        "atc_code": d.atc_code,
        "overview_en": d.overview_en,
        "overview_ar": d.overview_ar,
        "mechanism_en": d.mechanism_en,
        "mechanism_ar": d.mechanism_ar,
        "verification_status": d.verification_status,
        "is_demo": d.is_demo,
        "record_version": d.record_version,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def _product_dict(p: Product) -> Dict[str, Any]:
    return {
        "id": p.id,
        "drug_id": p.drug_id,
        "brand_name_en": p.brand_name_en,
        "brand_name_ar": p.brand_name_ar,
        "strength": p.strength,
        "strength_value": p.strength_value,
        "strength_unit": p.strength_unit,
        "dosage_form": p.dosage_form,
        "route": p.route,
        "manufacturer_id": p.manufacturer_id,
        "barcode": p.barcode,
        "registration_number": p.registration_number,
        "verification_status": p.verification_status,
        "is_demo": p.is_demo,
        "record_version": p.record_version,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def pull_changes(
    db: Session,
    *,
    user_id: Optional[str],
    device_id: str,
    entity_type: str,
    since: Optional[datetime] = None,
    system_ids: Optional[List[str]] = None,
    limit: int = PAGE_SIZE,
) -> PullPage:
    model = _SYNCABLE.get(entity_type)
    if model is None:
        return PullPage(entity_type, [], False, 0, [])

    state = db.execute(
        select(DeviceSyncState).where(
            DeviceSyncState.user_id == (user_id or ""), DeviceSyncState.device_id == device_id
        )
    ).scalar_one_or_none()
    watermark = since or (state.last_synced_at if state else None)

    stmt = select(model).order_by(model.updated_at).limit(limit + 1)
    if watermark:
        stmt = stmt.where(model.updated_at > watermark)
    if entity_type == "drug" and system_ids:
        from app.models import DrugClassification

        stmt = stmt.where(
            model.id.in_(select(DrugClassification.drug_id).where(DrugClassification.body_system_id.in_(system_ids)))
        )

    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [_drug_dict(r) if entity_type == "drug" else _product_dict(r) for r in rows]
    deleted = [str(r.id) for r in rows if getattr(r, "status", "active") == "deleted"]
    server_version = max((r.record_version or 1) for r in rows) if rows else (state.server_version if state else 0)

    # register/refresh the device so /sync/status reflects it
    if state is None:
        state = DeviceSyncState(user_id=user_id or "", device_id=device_id)
        db.add(state)
    if rows:
        state.last_synced_at = utcnow()
    db.flush()

    return PullPage(entity_type, items, has_more, server_version, deleted)


def push_changes(
    db: Session,
    *,
    user_id: Optional[str],
    device_id: str,
    changes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply client changes through the sync queue with conflict detection.

    Each change: {entity_type, entity_id, operation, payload, local_version, base_version}
    """
    accepted = conflicts = failed = 0
    results: List[Dict[str, Any]] = []

    for change in changes:
        entity_type = change.get("entity_type", "")
        entity_id = change.get("entity_id", "")
        operation = change.get("operation", SyncOperation.UPDATE.value)
        payload = change.get("payload", {})
        base_version = int(change.get("base_version", 0) or 0)
        local_version = int(change.get("local_version", 0) or 0)

        item = SyncQueueItem(
            user_id=user_id,
            device_id=device_id,
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            payload=json.dumps(payload, ensure_ascii=False, default=str),
            local_version=local_version,
            server_version=base_version,
        )

        model = _SYNCABLE.get(entity_type)
        server_obj = db.get(model, entity_id) if model else None

        if server_obj is not None and (server_obj.record_version or 1) > base_version:
            # Server moved ahead of the client's base — conflict, never overwrite (§32).
            # base_version=0 counts as 'no knowledge of server state' → conflict on update.
            item.status = SyncStatus.CONFLICT.value
            item.last_error = (
                f"Server version {server_obj.record_version} is newer than client base {base_version}."
            )
            conflicts += 1
            results.append({
                "entity_type": entity_type, "entity_id": entity_id,
                "status": "conflict",
                "server_version": server_obj.record_version,
                "message": item.last_error,
            })
        else:
            item.status = SyncStatus.PENDING.value
            accepted += 1
            results.append({"entity_type": entity_type, "entity_id": entity_id, "status": "accepted"})

        if operation == SyncOperation.FAVORITE_ADD.value and user_id:
            existing = db.execute(
                select(Favorite).where(
                    Favorite.user_id == user_id,
                    Favorite.entity_type == "drug",
                    Favorite.entity_id == payload.get("entity_id", entity_id),
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(Favorite(user_id=user_id, entity_type="drug", entity_id=payload.get("entity_id", entity_id)))
                item.status = SyncStatus.COMPLETED.value
        elif operation == SyncOperation.FAVORITE_REMOVE.value and user_id:
            fav = db.execute(
                select(Favorite).where(
                    Favorite.user_id == user_id,
                    Favorite.entity_type == "drug",
                    Favorite.entity_id == payload.get("entity_id", entity_id),
                )
            ).scalar_one_or_none()
            if fav is not None:
                db.delete(fav)
                item.status = SyncStatus.COMPLETED.value

        db.add(item)

    # update device state
    state = db.execute(
        select(DeviceSyncState).where(
            DeviceSyncState.user_id == (user_id or ""), DeviceSyncState.device_id == device_id
        )
    ).scalar_one_or_none()
    if state is None:
        state = DeviceSyncState(user_id=user_id or "", device_id=device_id)
        db.add(state)
    state.last_synced_at = utcnow()
    state.status = SyncStatus.CONFLICT.value if conflicts else SyncStatus.COMPLETED.value
    db.flush()

    return {
        "accepted": accepted,
        "conflicts": conflicts,
        "failed": failed,
        "results": results,
        "server_time": utcnow().isoformat(),
    }
