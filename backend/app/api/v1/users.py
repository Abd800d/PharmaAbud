"""User administration (§28, §29) and drug-request workflow (§69)."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.errors import NotFoundError, ValidationFailed
from app.db.session import get_db
from app.models import AuditLog, DrugRequest, Role, User
from app.schemas.auth import RoleOut, UserOut, UserRoleUpdate
from app.schemas.common import AuditLogOut, Message
from app.services.audit import record_audit

users_router = APIRouter(prefix="/users", tags=["users"])
requests_router = APIRouter(prefix="/drug-requests", tags=["drug-requests"])


@users_router.get("", response_model=dict, dependencies=[Depends(require_permission("user.manage"))])
def list_users(db: Session = Depends(get_db), page: int = 1, limit: int = 25) -> dict:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    rows = db.scalars(select(User).order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)).all()
    items = []
    for u in rows:
        items.append({
            "id": u.id, "email": u.email, "full_name": u.full_name,
            "is_active": u.is_active, "is_verified": u.is_verified,
            "roles": [{"code": r.code, "name_en": r.name_en} for r in u.roles],
            "created_at": u.created_at.isoformat(),
        })
    return {"items": items, "total": total, "page": page, "limit": limit, "has_more": page * limit < total}


@users_router.get("/roles", response_model=List[RoleOut], dependencies=[Depends(require_permission("user.manage"))])
def list_roles(db: Session = Depends(get_db)) -> List[RoleOut]:
    return [RoleOut.model_validate(r) for r in db.scalars(select(Role).order_by(Role.code)).all()]


@users_router.put("/{user_id}/roles", response_model=Message,
                  dependencies=[Depends(require_permission("user.manage"))])
def set_user_roles(user_id: str, payload: UserRoleUpdate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> Message:
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("User", user_id)
    roles = db.scalars(select(Role).where(Role.code.in_(payload.role_codes))).all()
    previous = [r.code for r in target.roles]
    target.roles = list(roles)
    record_audit(db, action="role.changed", entity_type="user", entity_id=user_id, user_id=user.id,
                 previous_value=previous, new_value=payload.role_codes,
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return Message(message="Roles updated.")


@requests_router.post("", response_model=Message)
def create_drug_request(name: str, reason: str = "", name_ar: str = "",
                        db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> Message:
    db.add(DrugRequest(requester_id=user.id, requested_name=name, requested_name_ar=name_ar, reason=reason))
    db.flush()
    return Message(message="Drug request submitted for review.")


@requests_router.get("", response_model=dict,
                     dependencies=[Depends(require_permission("drug.edit"))])
def list_drug_requests(db: Session = Depends(get_db), status: str = "") -> dict:
    stmt = select(DrugRequest).order_by(DrugRequest.created_at.desc()).limit(100)
    if status:
        stmt = stmt.where(DrugRequest.status == status)
    rows = db.scalars(stmt).all()
    return {"items": [{
        "id": r.id, "requested_name": r.requested_name, "requested_name_ar": r.requested_name_ar,
        "reason": r.reason, "status": r.status, "created_at": r.created_at.isoformat(),
    } for r in rows]}


@requests_router.patch("/{request_id}", response_model=Message,
                       dependencies=[Depends(require_permission("drug.edit"))])
def update_drug_request(request_id: str, status: str = "in_review",
                        resolution_notes: str = "", created_drug_id: str = "",
                        db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> Message:
    """Workflow (§69): submitted → in_review → researching →
    pending_pharmacist_review → approved → published | rejected."""
    allowed = {"submitted", "in_review", "researching", "pending_pharmacist_review",
               "approved", "published", "rejected"}
    if status not in allowed:
        raise ValidationFailed(f"Unknown status '{status}'. Allowed: {sorted(allowed)}")
    row = db.get(DrugRequest, request_id)
    if row is None:
        raise NotFoundError("DrugRequest", request_id)
    previous = row.status
    row.status = status
    row.reviewer_id = user.id
    if resolution_notes:
        row.resolution_notes = resolution_notes
    if created_drug_id:
        row.created_drug_id = created_drug_id
    record_audit(db, action="drug_request.status_changed", entity_type="drug_request",
                 entity_id=request_id, user_id=user.id,
                 previous_value=previous, new_value=status)
    db.flush()
    return Message(message=f"Request status: {previous} → {status}.")
