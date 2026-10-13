"""Audit log query + export (§95, §29).

The audit trail is append-only: there is deliberately NO create/update/delete
endpoint. Ordinary users can never modify or erase entries (§29).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.core.errors import ForbiddenError
from app.models import AuditLog, User

router = APIRouter(prefix="/audit-logs", tags=["audit"])

_READ_ACCESS = require_permission("audit.read")


def _filtered(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    user_id: str,
    date_from: Optional[datetime],
    date_to: Optional[datetime],
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if date_from:
        stmt = stmt.where(AuditLog.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.timestamp <= date_to)
    return stmt


@router.get("", dependencies=[Depends(_READ_ACCESS)])
def list_audit_logs(
    db: Session = Depends(get_db),
    action: str = "",
    entity_type: str = "",
    entity_id: str = "",
    user_id: str = "",
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """Filterable, sortable, paginated audit trail (§95)."""
    stmt = _filtered(db, action, entity_type, entity_id, user_id, date_from, date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = AuditLog.timestamp.asc() if sort == "asc" else AuditLog.timestamp.desc()
    rows = db.scalars(stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "user_id": r.user_id,
                "previous_value": r.previous_value,
                "new_value": r.new_value,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "sort": sort,
        "note": "Audit logs are append-only and cannot be modified or deleted (§29).",
    }


@router.get("/export.csv")
def export_audit_logs_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    action: str = "",
    entity_type: str = "",
    entity_id: str = "",
    user_id: str = "",
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Response:
    """CSV export of the filtered audit trail (§95 export, §82 governed export).

    The export itself is audit-logged.
    """
    if not (user.has_permission("data.export") or user.has_permission("settings.manage")):
        raise ForbiddenError("data.export permission required for audit export")
    from app.services.audit import record_audit

    stmt = _filtered(db, action, entity_type, entity_id, user_id, date_from, date_to).order_by(
        AuditLog.timestamp.desc()
    )
    rows = db.scalars(stmt.limit(50000)).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "action", "entity_type", "entity_id", "user_id", "previous_value", "new_value"])
    for r in rows:
        writer.writerow([
            r.timestamp.isoformat(), r.action, r.entity_type, r.entity_id,
            r.user_id or "", (r.previous_value or "")[:500], (r.new_value or "")[:500],
        ])
    record_audit(db, action="audit.exported", entity_type="audit_log", user_id=user.id,
                 new_value=f"{len(rows)} rows")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=aph_audit_log.csv"},
    )
