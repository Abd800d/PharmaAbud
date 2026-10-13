"""Operational tables: imports, verification, audit, favorites, sync, requests.

Audit logs are append-only — ordinary users can never modify them (§29).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import (
    ImportRowStatus,
    ImportStatus,
    SyncOperation,
    SyncStatus,
    Timestamped,
    UUIDPk,
    utcnow,
)


class Import(Base, UUIDPk, Timestamped):
    __tablename__ = "imports"

    filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    file_format: Mapped[str] = mapped_column(String(32), default="csv", nullable=False)  # csv|xlsx|json|xml|zip|sqlite|pg_dump|api
    status: Mapped[str] = mapped_column(String(48), default=ImportStatus.UPLOADED.value, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="product", nullable=False)  # drug|product
    column_mapping: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="import_record", cascade="all, delete-orphan", passive_deletes=True
    )


class ImportRow(Base, UUIDPk):
    __tablename__ = "import_rows"

    import_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # original values as JSON
    normalized_data: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String(48), default=ImportRowStatus.PENDING.value, nullable=False, index=True)
    duplicate_kind: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    duplicate_of_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_entity_id: Mapped[str] = mapped_column(String(36), default="", nullable=False)

    import_record: Mapped[Import] = relationship(back_populates="rows", lazy="selectin")


class ImportErrorRecord(Base, UUIDPk):
    __tablename__ = "import_errors"

    import_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    field: Mapped[str] = mapped_column(String(96), default="", nullable=False)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_correction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class VerificationRecord(Base, UUIDPk, Timestamped):
    """Verification workflow transitions + version history (§23, §59)."""

    __tablename__ = "verification_records"

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # drug|product|image|source|translation
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    previous_status: Mapped[str] = mapped_column(String(48), default="", nullable=False)
    new_status: Mapped[str] = mapped_column(String(48), default="", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    snapshot: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON snapshot of record at review


class AuditLog(Base, UUIDPk):
    """Append-only audit trail. No API ever updates or deletes these rows."""

    __tablename__ = "audit_logs"

    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # e.g. drug.created, drug.verified
    entity_type: Mapped[str] = mapped_column(String(48), default="", nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), default="", nullable=False, index=True)
    previous_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    new_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    device_metadata: Mapped[str] = mapped_column(String(512), default="", nullable=False)

    user = relationship("User", back_populates="audit_logs", lazy="selectin")


class Favorite(Base, UUIDPk, Timestamped):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_favorite"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="drug", nullable=False)  # drug|product
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    folder: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class RecentSearch(Base, UUIDPk, Timestamped):
    __tablename__ = "recent_searches"

    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)


class SearchTermStat(Base, UUIDPk):
    """Privacy-conscious aggregate analytics (§67). No per-user search storage."""

    __tablename__ = "search_term_stats"
    __table_args__ = (UniqueConstraint("term_normalized", "language", name="uq_search_term"),)

    term: Mapped[str] = mapped_column(String(255), nullable=False)
    term_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    zero_results: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SyncQueueItem(Base, UUIDPk, Timestamped):
    """Server-side sync queue (also mirrored on-device in SQLite)."""

    __tablename__ = "sync_queue"

    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    operation: Mapped[str] = mapped_column(String(32), default=SyncOperation.UPDATE.value, nullable=False)
    payload: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=SyncStatus.PENDING.value, nullable=False, index=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    server_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    local_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DeviceSyncState(Base, UUIDPk, Timestamped):
    __tablename__ = "device_sync_state"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    server_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dataset_mode: Mapped[str] = mapped_column(String(32), default="essential", nullable=False)  # essential|system|full
    downloaded_systems: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON list of system slugs
    status: Mapped[str] = mapped_column(String(32), default=SyncStatus.COMPLETED.value, nullable=False)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)


class DrugRequest(Base, UUIDPk, Timestamped):
    """User 'Request New Drug' workflow (§69)."""

    __tablename__ = "drug_requests"

    requester_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_name_ar: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(48), default="submitted", nullable=False, index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    created_drug_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="SET NULL"), nullable=True)
