"""Audit logging service. Append-only (§29)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import AuditLog

_audit_logger = get_logger("audit")


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    user_id: Optional[str] = None,
    previous_value: Any = "",
    new_value: Any = "",
    ip_address: str = "",
    device_metadata: str = "",
) -> AuditLog:
    """Persist an audit entry. Values are truncated to avoid unbounded rows."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ""),
        previous_value=_truncate(previous_value),
        new_value=_truncate(new_value),
        ip_address=ip_address or "",
        device_metadata=(device_metadata or "")[:512],
    )
    db.add(entry)
    db.flush()
    _audit_logger.info("audit action=%s entity=%s:%s user=%s", action, entity_type, entity_id, user_id)
    return entry


def _truncate(value: Any, limit: int = 20000) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        import json

        s = json.dumps(value, ensure_ascii=False, default=str)
    else:
        s = str(value)
    return s[:limit]
