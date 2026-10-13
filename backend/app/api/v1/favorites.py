"""Favorites API (§34) — server-side mirror of the device favorites.

Device favorites work fully offline; when signed in, the sync engine
reconciles them through the sync queue (favorite_add / favorite_remove).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import Drug, Favorite, Product, User
from app.schemas.common import Message
from app.services.audit import record_audit

router = APIRouter(prefix="/favorites", tags=["favorites"])


class FavoriteIn(BaseModel):
    entity_type: str = Field(default="drug", pattern="^(drug|product)$")
    entity_id: str
    folder: str = ""


@router.get("", response_model=dict)
def list_favorites(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    rows = db.scalars(select(Favorite).where(Favorite.user_id == user.id)
                      .order_by(Favorite.sort_order, Favorite.created_at.desc())).all()
    items = []
    for fav in rows:
        label = ""
        if fav.entity_type == "drug":
            d = db.get(Drug, fav.entity_id)
            label = (d.generic_name_en if d else "") or ""
        else:
            p = db.get(Product, fav.entity_id)
            label = (p.brand_name_en if p else "") or ""
        items.append({
            "id": fav.id, "entity_type": fav.entity_type, "entity_id": fav.entity_id,
            "label": label, "folder": fav.folder,
            "created_at": fav.created_at.isoformat(),
        })
    return {"items": items, "total": len(items)}


@router.post("", response_model=Message)
def add_favorite(payload: FavoriteIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> Message:
    model = Drug if payload.entity_type == "drug" else Product
    if db.get(model, payload.entity_id) is None:
        raise NotFoundError(payload.entity_type.title(), payload.entity_id)
    existing = db.scalar(select(Favorite).where(
        Favorite.user_id == user.id, Favorite.entity_type == payload.entity_type,
        Favorite.entity_id == payload.entity_id,
    ))
    if existing is None:
        db.add(Favorite(user_id=user.id, entity_type=payload.entity_type,
                        entity_id=payload.entity_id, folder=payload.folder))
    db.flush()
    return Message(message="Added to favorites.")


@router.delete("/{entity_type}/{entity_id}", response_model=Message)
def remove_favorite(entity_type: str, entity_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)) -> Message:
    fav = db.scalar(select(Favorite).where(
        Favorite.user_id == user.id, Favorite.entity_type == entity_type,
        Favorite.entity_id == entity_id,
    ))
    if fav is None:
        raise NotFoundError("Favorite", entity_id)
    db.delete(fav)
    db.flush()
    return Message(message="Removed from favorites.")
