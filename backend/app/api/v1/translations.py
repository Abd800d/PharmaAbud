"""Translation management endpoints (§58, §92).

Translator dashboard backing API: list EN/AR field pairs with status, edit
translations, approve human reviews. Machine translations are marked and
MUST NOT overwrite original source text.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import Translation, TranslationStatus, User, utcnow
from app.schemas.common import Message
from app.services.audit import record_audit

router = APIRouter(prefix="/translations", tags=["translations"])


class TranslationCreate(BaseModel):
    entity_type: str = Field(..., pattern="^(drug|product|source)$")
    entity_id: str
    field: str = Field(..., min_length=1, max_length=96)
    language: str = Field(..., pattern="^(en|ar)$")
    original_text: str = ""
    translated_text: str = ""
    status: str = Field(default=TranslationStatus.MACHINE_TRANSLATED.value,
                        pattern="^(original|human_reviewed|machine_translated|needs_review|missing)$")


class TranslationUpdate(BaseModel):
    translated_text: str
    status: Optional[str] = Field(default=None,
                                  pattern="^(original|human_reviewed|machine_translated|needs_review|missing)$")


@router.get("", response_model=dict)
def list_translations(
    db: Session = Depends(get_db),
    entity_type: str = "",
    entity_id: str = "",
    status: str = "",
    language: str = "",
    page: int = 1,
    limit: int = 50,
    user: User = Depends(get_current_user),
) -> dict:
    stmt = select(Translation)
    if entity_type:
        stmt = stmt.where(Translation.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(Translation.entity_id == entity_id)
    if status:
        stmt = stmt.where(Translation.status == status)
    if language:
        stmt = stmt.where(Translation.language == language)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Translation.updated_at.desc()).offset((page - 1) * limit).limit(limit)).all()
    return {
        "items": [{
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "field": r.field, "language": r.language,
            "original_text": r.original_text, "translated_text": r.translated_text,
            "status": r.status, "reviewed_by": r.reviewed_by,
            "updated_at": r.updated_at.isoformat(),
        } for r in rows],
        "total": total, "page": page, "limit": limit, "has_more": page * limit < total,
        "note": "Machine-translated content must be human-reviewed before use in verified records (§58).",
    }


@router.post("", response_model=Message,
             dependencies=[Depends(require_permission("drug.edit"))])
def create_translation(payload: TranslationCreate, request: Request, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> Message:
    existing = db.scalar(select(Translation).where(
        Translation.entity_type == payload.entity_type,
        Translation.entity_id == payload.entity_id,
        Translation.field == payload.field,
        Translation.language == payload.language,
    ))
    if existing is not None:
        # never overwrite original source text (§92)
        existing.translated_text = payload.translated_text
        existing.status = payload.status
    else:
        db.add(Translation(**payload.model_dump()))
    record_audit(db, action="translation.created", entity_type=payload.entity_type,
                 entity_id=payload.entity_id, user_id=user.id,
                 new_value=f"{payload.field}/{payload.language}:{payload.status}")
    db.flush()
    return Message(message="Translation saved.")


@router.put("/{translation_id}", response_model=Message,
            dependencies=[Depends(require_permission("drug.edit"))])
def update_translation(translation_id: str, payload: TranslationUpdate, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Message:
    row = db.get(Translation, translation_id)
    if row is None:
        raise NotFoundError("Translation", translation_id)
    row.translated_text = payload.translated_text
    if payload.status:
        row.status = payload.status
    record_audit(db, action="translation.updated", entity_type=row.entity_type,
                 entity_id=row.entity_id, user_id=user.id,
                 new_value=f"{row.field}/{row.language}:{row.status}")
    db.flush()
    return Message(message="Translation updated (original text preserved).")


@router.post("/{translation_id}/approve", response_model=Message,
             dependencies=[Depends(require_permission("drug.edit"))])
def approve_translation(translation_id: str, request: Request, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> Message:
    row = db.get(Translation, translation_id)
    if row is None:
        raise NotFoundError("Translation", translation_id)
    previous = row.status
    row.status = TranslationStatus.HUMAN_REVIEWED.value
    row.reviewed_by = user.id
    record_audit(db, action="translation.approved", entity_type=row.entity_type,
                 entity_id=row.entity_id, user_id=user.id,
                 previous_value=previous, new_value=row.status)
    db.flush()
    return Message(message="Translation marked as human-reviewed.")


@router.get("/stats", response_model=dict,
            dependencies=[Depends(require_permission("drug.edit"))])
def translation_stats(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(Translation.status, func.count()).group_by(Translation.status)).all()
    missing_ar = db.scalar(select(func.count()).select_from(
        select(Translation).where(Translation.language == "ar").subquery()
    )) or 0
    return {
        "by_status": {r[0]: r[1] for r in rows},
        "arabic_entries": missing_ar,
        "note": "Machine translations must be reviewed before verification (§58).",
    }
