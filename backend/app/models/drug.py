"""Drug (generic/scientific entity) and its monograph content tables.

Scientific information lives ONLY on the drug — never duplicated across
commercial products (§5). Bilingual columns: *_en / _ar.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import Timestamped, UUIDPk, VerificationStatus, Versioned


class Drug(Base, UUIDPk, Timestamped, Versioned):
    __tablename__ = "drugs"

    generic_name_en: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    generic_name_ar: Mapped[str] = mapped_column(String(255), default="", nullable=False, index=True)
    scientific_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    pronunciation: Mapped[str] = mapped_column(String(255), default="", nullable=False)  # English only, verified or empty
    drug_class: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    pharmacological_class_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    therapeutic_class_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    drug_category: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    atc_code: Mapped[str] = mapped_column(String(32), default="", nullable=False, index=True)
    cas_number: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    molecular_formula: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    molecular_weight: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    overview_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    overview_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mechanism_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mechanism_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pharmacodynamics_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pharmacodynamics_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pharmacokinetics_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pharmacokinetics_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    absorption_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    absorption_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    distribution_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    distribution_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metabolism_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metabolism_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    elimination_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    elimination_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    half_life: Mapped[str] = mapped_column(String(128), default="", nullable=False)

    is_combination: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(48), default=VerificationStatus.DRAFT.value, nullable=False, index=True
    )
    search_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    search_text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)

    synonyms: Mapped[list["DrugSynonym"]] = relationship(back_populates="drug", cascade="all, delete-orphan", lazy="selectin")
    classifications: Mapped[list["DrugClassification"]] = relationship(  # noqa: F821
        back_populates="drug", cascade="all, delete-orphan", lazy="selectin"
    )
    products: Mapped[list["Product"]] = relationship(  # noqa: F821
        back_populates="drug", cascade="all, delete-orphan", lazy="selectin"
    )


class DrugSynonym(Base, UUIDPk):
    __tablename__ = "drug_synonyms"
    __table_args__ = (UniqueConstraint("drug_id", "term", "language", name="uq_drug_synonym"),)

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    term: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    normalized_term: Mapped[str] = mapped_column(String(255), default="", nullable=False, index=True)

    drug: Mapped[Drug] = relationship(back_populates="synonyms", lazy="selectin")


class DrugIndication(Base, UUIDPk):
    __tablename__ = "drug_indications"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_off_label: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugContraindication(Base, UUIDPk):
    __tablename__ = "drug_contraindications"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="absolute", nullable=False)  # absolute | relative
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugWarning(Base, UUIDPk):
    __tablename__ = "drug_warnings"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="warning", nullable=False)  # boxed | warning | notice
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugPrecaution(Base, UUIDPk):
    __tablename__ = "drug_precautions"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugSideEffect(Base, UUIDPk):
    __tablename__ = "drug_side_effects"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    frequency: Mapped[str] = mapped_column(String(64), default="", nullable=False)  # e.g. common, rare — per source wording
    is_serious: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugInteraction(Base, UUIDPk):
    __tablename__ = "drug_interactions"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    interacting_agent: Mapped[str] = mapped_column(String(255), default="", nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    mechanism_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugFoodInteraction(Base, UUIDPk):
    __tablename__ = "drug_food_interactions"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugDosage(Base, UUIDPk):
    """Dose rows. NEVER invented: when unverified, `text_en` must read
    "Not available / Requires verified source" (§6)."""

    __tablename__ = "drug_dosages"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    population: Mapped[str] = mapped_column(String(48), default="adult", nullable=False)  # adult|pediatric|geriatric|renal|hepatic
    indication: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    route: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    dose_value: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    dose_unit: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    frequency: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    max_dose: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    duration: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugPregnancy(Base, UUIDPk):
    __tablename__ = "drug_pregnancy"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risk_label: Mapped[str] = mapped_column(String(128), default="", nullable=False)  # preserve source terminology
    risk_system: Mapped[str] = mapped_column(String(128), default="", nullable=False)  # e.g. "FDA 2015 Lactation rule", not old A-X
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    last_verified_date: Mapped[str] = mapped_column(String(32), default="", nullable=False)


class DrugLactation(Base, UUIDPk):
    __tablename__ = "drug_lactation"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    milk_transfer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    infant_considerations: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)


class DrugMonitoring(Base, UUIDPk):
    __tablename__ = "drug_monitoring"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugAdministration(Base, UUIDPk):
    __tablename__ = "drug_administration"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DrugOverdose(Base, UUIDPk):
    __tablename__ = "drug_overdose"

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    text_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)


class DrugAlternative(Base, UUIDPk):
    """Therapeutic alternatives: DIFFERENT active ingredients that may be used
    for similar clinical purposes. Distinct from pharmaceutical equivalents
    (same ingredient products) which are derived dynamically from products."""

    __tablename__ = "drug_alternatives"
    __table_args__ = (UniqueConstraint("drug_id", "alternative_drug_id", name="uq_drug_alternative"),)

    drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    alternative_drug_id: Mapped[str] = mapped_column(String(36), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    rationale_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rationale_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_level: Mapped[str] = mapped_column(String(64), default="", nullable=False)
