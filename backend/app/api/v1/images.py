"""Image review endpoints (§91)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import ProductImage, User, VerificationStatus
from app.schemas.common import Message
from app.services.audit import record_audit

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/review-queue", dependencies=[Depends(require_permission("image.approve"))])
def review_queue(db: Session = Depends(get_db), page: int = 1, limit: int = 25) -> dict:
    total = db.scalar(
        select(func.count()).select_from(ProductImage).where(
            ProductImage.verification_status == VerificationStatus.PENDING_VERIFICATION.value
        )
    ) or 0
    rows = db.scalars(
        select(ProductImage)
        .where(ProductImage.verification_status == VerificationStatus.PENDING_VERIFICATION.value)
        .order_by(ProductImage.created_at)
        .offset((page - 1) * limit).limit(limit)
    ).all()
    return {
        "items": [{
            "id": img.id, "product_id": img.product_id, "kind": img.kind,
            "storage_path": img.storage_path, "thumbnail_path": img.thumbnail_path,
            "file_type": img.file_type, "width": img.width, "height": img.height,
            "source": img.source, "uploaded_by": img.uploaded_by,
            "created_at": img.created_at.isoformat(),
            "verification_status": img.verification_status,
        } for img in rows],
        "total": total, "page": page, "limit": limit, "has_more": page * limit < total,
    }


@router.post("/{image_id}/approve", response_model=Message,
             dependencies=[Depends(require_permission("image.approve"))])
def approve_image(image_id: str, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> Message:
    img = db.get(ProductImage, image_id)
    if img is None:
        raise NotFoundError("Image", image_id)
    img.verification_status = VerificationStatus.VERIFIED.value
    record_audit(db, action="image.approved", entity_type="image", entity_id=image_id, user_id=user.id)
    db.flush()
    return Message(message="Image approved.")


@router.post("/{image_id}/reject", response_model=Message,
             dependencies=[Depends(require_permission("image.approve"))])
def reject_image(image_id: str, reason: str = "", request: Request = None,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Message:
    img = db.get(ProductImage, image_id)
    if img is None:
        raise NotFoundError("Image", image_id)
    img.verification_status = VerificationStatus.REJECTED.value
    record_audit(db, action="image.rejected", entity_type="image", entity_id=image_id,
                 user_id=user.id, new_value=reason)
    db.flush()
    return Message(message="Image rejected.")
