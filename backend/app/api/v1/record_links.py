"""Record links: Equivalent Products (§11) + duplicate-link review (§16, §111).

CRITICAL semantics:
- `link_type="equivalent"` is labelled EXACTLY "Equivalent Product" — it is
  NEVER "therapeutic alternative" and NEVER clinical interchangeability.
- Uncertain links require human review; records are NEVER auto-merged (§16).
- §111 review metadata is exposed on every link: Linked by / Why / Checked By /
  Approved By / Approval Date.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.errors import NotFoundError, ValidationFailed
from app.db.session import get_db
from app.models import Product, RecordLink, User
from app.schemas.common import Message
from app.services.audit import record_audit

router = APIRouter(tags=["record-links"])

EQUIVALENT_LABEL = "Equivalent Product"


def _pack_link(link: RecordLink, label_a: str, label_b: str) -> dict:
    return {
        "id": link.id,
        "link_type": link.link_type,
        "label": EQUIVALENT_LABEL if link.link_type == "equivalent" else "Duplicate Candidate",
        "entity_a": {"type": link.entity_a_type, "id": link.entity_a_id, "label": label_a},
        "entity_b": {"type": link.entity_b_type, "id": link.entity_b_id, "label": label_b},
        "status": link.status,
        # §111 metadata — always present
        "linked_by": link.linked_by,
        "why": link.why,
        "checked_by": link.checked_by,
        "approved_by": link.approved_by,
        "approval_date": link.approval_date.isoformat() if link.approval_date else None,
        "notes": link.notes,
        "created_at": link.created_at.isoformat(),
    }


def _product_label(db: Session, product_id: str) -> str:
    p = db.get(Product, product_id)
    return (p.brand_name_en or p.brand_name_ar or product_id) if p else product_id


def _links_for(db: Session, product_id: str) -> list[RecordLink]:
    return list(db.scalars(
        select(RecordLink).where(
            RecordLink.link_type == "equivalent",
            or_(RecordLink.entity_a_id == product_id, RecordLink.entity_b_id == product_id),
        ).order_by(RecordLink.created_at.desc())
    ).all())


# ------------------------------------------------------------------ equivalents
@router.get("/products/{product_id}/equivalents")
def list_equivalents(product_id: str, db: Session = Depends(get_db)) -> dict:
    """Equivalent Products for a product (§11). Label is exactly
    "Equivalent Product" — not a therapeutic alternative."""
    if not db.get(Product, product_id):
        raise NotFoundError("Product", product_id)
    links = _links_for(db, product_id)
    return {
        "label": EQUIVALENT_LABEL,
        "note": (
            "'Equivalent Product' means product-record equivalence only (same active "
            "ingredient/strength/form class). It does NOT mean clinically interchangeable "
            "and is NOT therapeutic substitution advice."
        ),
        "items": [
            _pack_link(
                l,
                _product_label(db, l.entity_a_id),
                _product_label(db, l.entity_b_id),
            )
            for l in links
        ],
    }


@router.post("/products/{product_id}/equivalents", response_model=Message,
             dependencies=[Depends(require_permission("product.edit"))])
def create_equivalent(product_id: str, target_product_id: str, why: str = "",
                      notes: str = "", db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)) -> Message:
    """Link two products as Equivalent Products (§11). The link starts as
    `pending` — human review is required before it is trusted (§16)."""
    if target_product_id == product_id:
        raise ValidationFailed("A product cannot be linked to itself.")
    for pid in (product_id, target_product_id):
        if not db.get(Product, pid):
            raise NotFoundError("Product", pid)
    if not why.strip():
        raise ValidationFailed("'why' is required (§111: the reason for the link must be recorded).")
    a, b = sorted([product_id, target_product_id])
    existing = db.scalar(
        select(RecordLink).where(
            RecordLink.link_type == "equivalent",
            RecordLink.entity_a_id == a, RecordLink.entity_b_id == b,
        )
    )
    if existing:
        raise ValidationFailed("This Equivalent Product link already exists.")
    link = RecordLink(
        link_type="equivalent",
        entity_a_type="product", entity_a_id=a,
        entity_b_type="product", entity_b_id=b,
        status="pending",
        why=why.strip(), notes=notes.strip(),
        linked_by=user.id,
    )
    db.add(link)
    db.flush()
    record_audit(db, action="product.equivalent.linked", entity_type="product", entity_id=product_id,
                 user_id=user.id, new_value=f"{target_product_id} ({EQUIVALENT_LABEL}) — pending review")
    return Message(message=f"{EQUIVALENT_LABEL} link created — pending human review.")


# ------------------------------------------------------------------ review (§111)
@router.post("/record-links/{link_id}/review", response_model=Message,
             dependencies=[Depends(require_permission("product.verify"))])
def review_link(link_id: str, decision: str, notes: str = "",
                db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Message:
    """Approve or reject a record link (§111).

    On approval: Checked By + Approved By + Approval Date are recorded.
    On rejection: Checked By is recorded; the link stays visible as rejected.
    """
    if decision not in ("approve", "reject"):
        raise ValidationFailed("decision must be 'approve' or 'reject'.")
    link = db.get(RecordLink, link_id)
    if not link:
        raise NotFoundError("RecordLink", link_id)
    link.checked_by = user.id
    if decision == "approve":
        link.status = "approved"
        link.approved_by = user.id
        link.approval_date = datetime.utcnow()
    else:
        link.status = "rejected"
        link.approved_by = None
        link.approval_date = None
    if notes.strip():
        link.notes = (link.notes + "\n" if link.notes else "") + notes.strip()
    db.flush()
    record_audit(db, action=f"record_link.{decision}d", entity_type="record_link", entity_id=link.id,
                 user_id=user.id, new_value=decision,
                 previous_value="pending" if decision == "approve" else "")
    return Message(message=f"Record link {decision}d. Checked by: {user.email}.")


@router.get("/record-links", dependencies=[Depends(require_permission("product.edit"))])
def list_record_links(db: Session = Depends(get_db), status: str = "",
                      link_type: str = "", limit: int = 100) -> dict:
    """Review queue of duplicate/equivalence links with §111 metadata."""
    stmt = select(RecordLink).order_by(RecordLink.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(RecordLink.status == status)
    if link_type:
        stmt = stmt.where(RecordLink.link_type == link_type)
    links = db.scalars(stmt).all()
    return {
        "items": [
            _pack_link(l, _product_label(db, l.entity_a_id), _product_label(db, l.entity_b_id))
            for l in links
        ],
        "policy": "Never auto-merged (§16). Review metadata: Linked by / Why / Checked By / Approved By / Approval Date (§111).",
    }


@router.delete("/record-links/{link_id}", response_model=Message,
               dependencies=[Depends(require_permission("product.edit"))])
def delete_link(link_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> Message:
    link = db.get(RecordLink, link_id)
    if not link:
        raise NotFoundError("RecordLink", link_id)
    db.delete(link)
    db.flush()
    record_audit(db, action="record_link.deleted", entity_type="record_link", entity_id=link_id,
                 user_id=user.id)
    return Message(message="Record link removed.")
