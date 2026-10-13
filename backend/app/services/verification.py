"""Data verification workflow (§23, §59).

Statuses: draft → imported → imported_pending_review → pending_verification
→ verified | needs_update | rejected | archived

Every transition writes a VerificationRecord (version history) AND an
AuditLog. Only pharmacists+ (drug.verify permission) may mark Verified.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models import AuditLog, Drug, Product, Source, VerificationRecord, VerificationStatus, utcnow
from app.services.audit import record_audit

ALLOWED_TRANSITIONS: Dict[str, set[str]] = {
    VerificationStatus.DRAFT.value: {
        VerificationStatus.PENDING_VERIFICATION.value,
        VerificationStatus.IMPORTED_PENDING_REVIEW.value,
        VerificationStatus.ARCHIVED.value,
        VerificationStatus.REJECTED.value,
    },
    VerificationStatus.IMPORTED.value: {
        VerificationStatus.IMPORTED_PENDING_REVIEW.value,
        VerificationStatus.PENDING_VERIFICATION.value,
        VerificationStatus.REJECTED.value,
    },
    VerificationStatus.IMPORTED_PENDING_REVIEW.value: {
        VerificationStatus.PENDING_VERIFICATION.value,
        VerificationStatus.REJECTED.value,
        VerificationStatus.NEEDS_UPDATE.value,
    },
    VerificationStatus.PENDING_VERIFICATION.value: {
        VerificationStatus.VERIFIED.value,
        VerificationStatus.REJECTED.value,
        VerificationStatus.NEEDS_UPDATE.value,
    },
    VerificationStatus.VERIFIED.value: {
        VerificationStatus.NEEDS_UPDATE.value,
        VerificationStatus.ARCHIVED.value,
        VerificationStatus.REJECTED.value,
    },
    VerificationStatus.NEEDS_UPDATE.value: {
        VerificationStatus.PENDING_VERIFICATION.value,
        VerificationStatus.VERIFIED.value,
        VerificationStatus.ARCHIVED.value,
    },
    VerificationStatus.REJECTED.value: {
        VerificationStatus.DRAFT.value,
        VerificationStatus.ARCHIVED.value,
    },
    VerificationStatus.ARCHIVED.value: {
        VerificationStatus.DRAFT.value,
    },
}

_MODELS = {"drug": Drug, "product": Product, "source": Source}


def get_status(entity_type: str, entity_id: str, db: Session) -> str:
    model = _MODELS.get(entity_type)
    if model is None:
        raise ValidationFailed(f"Unknown entity type: {entity_type}")
    obj = db.get(model, entity_id)
    if obj is None:
        raise ValidationFailed(f"{entity_type} {entity_id} not found")
    return obj.verification_status


def transition(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    new_status: str,
    reviewer_id: Optional[str],
    notes: str = "",
    ip_address: str = "",
) -> VerificationRecord:
    model = _MODELS.get(entity_type)
    if model is None:
        raise ValidationFailed(f"Unknown entity type: {entity_type}")
    obj = db.get(model, entity_id)
    if obj is None:
        raise ValidationFailed(f"{entity_type} {entity_id} not found")

    current = obj.verification_status
    if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValidationFailed(
            f"Illegal verification transition: {current} → {new_status}",
            {"allowed": sorted(ALLOWED_TRANSITIONS.get(current, set()))},
        )

    snapshot = {}
    for col in obj.__table__.columns.keys():
        val = getattr(obj, col)
        if isinstance(val, (str, int, float, bool)) or val is None:
            snapshot[col] = val

    obj.verification_status = new_status
    if new_status == VerificationStatus.VERIFIED.value:
        obj.verified_at = utcnow()
        obj.verified_by = reviewer_id
    if hasattr(obj, "record_version"):
        obj.record_version = (obj.record_version or 1) + 1

    record = VerificationRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        previous_status=current,
        new_status=new_status,
        version=getattr(obj, "record_version", 1) or 1,
        reviewer_id=reviewer_id,
        review_date=utcnow(),
        notes=notes,
        snapshot=json.dumps(snapshot, ensure_ascii=False, default=str),
    )
    db.add(record)

    record_audit(
        db,
        action=f"{entity_type}.verification.{new_status}",
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=reviewer_id,
        previous_value=current,
        new_value=new_status,
        ip_address=ip_address,
    )
    db.flush()
    return record


def history(db: Session, entity_type: str, entity_id: str, limit: int = 50):
    return (
        db.query(VerificationRecord)
        .filter(VerificationRecord.entity_type == entity_type, VerificationRecord.entity_id == entity_id)
        .order_by(VerificationRecord.created_at.desc())
        .limit(limit)
        .all()
    )
