"""Source registry, source-linked data, and translation tracking.

Sources carry type + license metadata; authority is NOT uniform across
sources (§24). Field-level source links support provenance (§25).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import SourceType, Timestamped, TranslationStatus, UUIDPk, VerificationStatus, Versioned


class Source(Base, UUIDPk, Timestamped, Versioned):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    source_type: Mapped[str] = mapped_column(String(48), default=SourceType.OTHER.value, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    publication_date: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    retrieved_date: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    license_info: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(48), default=VerificationStatus.PENDING_VERIFICATION.value, nullable=False, index=True
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DrugSource(Base, UUIDPk):
    """Drug <-> source link (record-level)."""

    __tablename__ = "drug_sources"
    __table_args__ = (UniqueConstraint("drug_id", "source_id", "section", name="uq_drug_source_section"),)

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(64), default="record", nullable=False)  # dose|pregnancy|mechanism|record|...
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source = relationship("Source", lazy="selectin")


class ProductSource(Base, UUIDPk):
    __tablename__ = "product_sources"
    __table_args__ = (UniqueConstraint("product_id", "source_id", "section", name="uq_product_source_section"),)

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drug_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(64), default="record", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source = relationship("Source", lazy="selectin")


class ContentSource(Base, UUIDPk):
    """Field/section-level source reference (§25).

    entity_type: drug|product ; entity_id: record id ;
    section: e.g. 'dosage.adult', 'pregnancy', 'mechanism'
    """

    __tablename__ = "content_sources"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "section", "source_id", name="uq_content_source"),
    )

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    quote: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source = relationship("Source", lazy="selectin")


class Translation(Base, UUIDPk, Timestamped):
    """Translation tracking. Machine translations are marked and must be
    human-reviewed before being treated as verified content (§58)."""

    __tablename__ = "translations"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "field", "language", name="uq_translation"),
    )

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(96), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=TranslationStatus.MISSING.value, nullable=False, index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
