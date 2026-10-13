"""Taxonomy & catalog tables.

Hierarchy: Body System -> Therapeutic Group -> Pharmacological Class -> Drug -> Product.
Drugs may belong to multiple systems/classes when medically justified (§70).
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import Bilingual, Timestamped, UUIDPk, Versioned


class BodySystem(Base, UUIDPk, Timestamped, Bilingual, Versioned):
    """One of the 18 primary medical systems (§4)."""

    __tablename__ = "body_systems"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    icon: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    therapeutic_groups: Mapped[list["TherapeuticGroup"]] = relationship(back_populates="body_system", lazy="selectin")


class TherapeuticGroup(Base, UUIDPk, Timestamped, Bilingual, Versioned):
    __tablename__ = "therapeutic_groups"

    body_system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("body_systems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    description_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    body_system: Mapped[BodySystem] = relationship(back_populates="therapeutic_groups", lazy="selectin")
    pharmacological_classes: Mapped[list["PharmacologicalClass"]] = relationship(
        back_populates="therapeutic_group", lazy="selectin"
    )


class PharmacologicalClass(Base, UUIDPk, Timestamped, Bilingual, Versioned):
    __tablename__ = "pharmacological_classes"

    therapeutic_group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("therapeutic_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    description_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    therapeutic_group: Mapped[TherapeuticGroup] = relationship(back_populates="pharmacological_classes", lazy="selectin")


class DrugClassification(Base, UUIDPk):
    """Drug <-> classification assignment. A drug can appear in multiple
    systems / groups / classes when scientifically justified."""

    __tablename__ = "drug_classifications"
    __table_args__ = (
        UniqueConstraint("drug_id", "pharmacological_class_id", name="uq_drug_pharm_class"),
    )

    drug_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pharmacological_class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pharmacological_classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body_system_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("body_systems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    therapeutic_group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("therapeutic_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    drug = relationship("Drug", back_populates="classifications", lazy="selectin")


class DosageForm(Base, UUIDPk, Timestamped, Bilingual):
    """Normalized dosage-form taxonomy (§8). Administrators may extend it."""

    __tablename__ = "dosage_forms"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Route(Base, UUIDPk, Timestamped, Bilingual):
    __tablename__ = "routes"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Country(Base, UUIDPk, Timestamped, Bilingual):
    __tablename__ = "countries"

    iso_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Manufacturer(Base, UUIDPk, Timestamped, Versioned):
    __tablename__ = "manufacturers"

    name_en: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name_ar: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    country_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("countries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    website: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    search_text: Mapped[str] = mapped_column(Text, default="", nullable=False, index=True)
