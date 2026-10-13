"""Shared column mixins and enumerations."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ------------------------------------------------------------------ enums
class VerificationStatus(str, enum.Enum):
    DRAFT = "draft"
    IMPORTED = "imported"
    IMPORTED_PENDING_REVIEW = "imported_pending_review"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    NEEDS_UPDATE = "needs_update"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class RecordStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class SourceType(str, enum.Enum):
    REGULATORY = "regulatory"           # FDA, EMA, national agencies
    OFFICIAL_LABEL = "official_label"   # DailyMed, official product docs
    REFERENCE = "reference"             # formularies, PubChem, MedlinePlus, WHO
    MANUFACTURER = "manufacturer"
    IMPORTED = "imported"
    DEMO = "demo"
    OTHER = "other"


class ImageKind(str, enum.Enum):
    FRONT_PACKAGE = "front_package"
    BACK_PACKAGE = "back_package"
    SIDE_PACKAGE = "side_package"
    BLISTER = "blister"
    BOTTLE = "bottle"
    LABEL = "label"
    LEAFLET = "leaflet"
    OTHER = "other"


class ImportStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    MAPPED = "mapped"
    IMPORTING = "importing"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLED = "cancelled"


class ImportRowStatus(str, enum.Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    DUPLICATE_EXACT = "duplicate_exact"
    DUPLICATE_POSSIBLE = "duplicate_possible"
    DUPLICATE_POTENTIAL = "duplicate_potential"
    IMPORTED = "imported"
    SKIPPED = "skipped"
    FAILED = "failed"


class DuplicateKind(str, enum.Enum):
    EXACT = "exact"
    POSSIBLE = "possible"
    POTENTIAL = "potential"


class DrugRequestStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    RESEARCHING = "researching"
    PENDING_PHARMACIST_REVIEW = "pending_pharmacist_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class SyncOperation(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    FAVORITE_ADD = "favorite_add"
    FAVORITE_REMOVE = "favorite_remove"


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class TranslationStatus(str, enum.Enum):
    ORIGINAL = "original"
    HUMAN_REVIEWED = "human_reviewed"
    MACHINE_TRANSLATED = "machine_translated"
    NEEDS_REVIEW = "needs_review"
    MISSING = "missing"


# ------------------------------------------------------------------ mixins
class UUIDPk:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True)


class Versioned:
    """Version + audit columns required on major records (§59)."""

    record_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_source_update: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Bilingual:
    """English + Arabic name columns. Arabic is a first-class field, not a string layer."""

    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False, default="")


__all__ = [
    "utcnow", "new_uuid",
    "VerificationStatus", "RecordStatus", "SourceType", "ImageKind",
    "ImportStatus", "ImportRowStatus", "DuplicateKind", "DrugRequestStatus",
    "SyncOperation", "SyncStatus", "TranslationStatus",
    "UUIDPk", "Timestamped", "Versioned", "Bilingual",
]
