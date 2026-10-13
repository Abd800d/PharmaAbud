"""Automated data-quality checks (§57).

The quality score is a DATA-COMPLETENESS indicator only. It is explicitly
NOT a medical reliability score (§57).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Drug,
    DrugDosage,
    DrugInteraction,
    DrugPregnancy,
    DrugSource,
    ImportRow,
    Product,
    ProductImage,
    Source,
)


@dataclass
class QualityIssue:
    code: str
    severity: str            # error | warning | info
    entity_type: str
    entity_id: str
    entity_label: str
    message: str


@dataclass
class QualityReport:
    total_records: int
    issues: List[QualityIssue]
    score: float  # 0-100 completeness score, NOT medical reliability
    summary: Dict[str, int] = field(default_factory=dict)
    metrics: Dict[str, int] = field(default_factory=dict)  # §57 dashboard metrics


def collect_metrics(db: Session) -> Dict[str, int]:
    """Aggregate data-quality metrics for the dashboard (§57)."""
    def cnt(stmt) -> int:
        return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    dosage_ids = select(DrugDosage.drug_id).distinct()
    inter_ids = select(DrugInteraction.drug_id).distinct()
    preg_ids = select(DrugPregnancy.drug_id).distinct()
    src_ids = select(DrugSource.drug_id).distinct()
    img_ids = select(ProductImage.product_id).distinct()

    return {
        "missing_sources": cnt(select(Drug).where(~Drug.id.in_(src_ids))),
        "unverified_content": cnt(select(Drug).where(Drug.verification_status != "verified"))
        + cnt(select(Product).where(Product.verification_status != "verified")),
        "duplicate_candidates": cnt(select(ImportRow).where(ImportRow.duplicate_kind != "")),
        "missing_images": cnt(select(Product).where(~Product.id.in_(img_ids))),
        "missing_dosage": cnt(select(Drug).where(~Drug.id.in_(dosage_ids))),
        "missing_interactions": cnt(select(Drug).where(~Drug.id.in_(inter_ids))),
        "missing_pregnancy": cnt(select(Drug).where(~Drug.id.in_(preg_ids))),
        "missing_brand_names": cnt(select(Product).where(
            (Product.brand_name_en == "") & (Product.brand_name_ar == "")
        )),
        "missing_generic_names": cnt(select(Drug).where(
            (Drug.generic_name_en == "") & (Drug.generic_name_ar == "")
        )),
        "missing_arabic_translations": cnt(select(Drug).where(Drug.generic_name_ar == ""))
        + cnt(select(Product).where(Product.brand_name_ar == "")),
    }


def run_quality_checks(db: Session, limit: int = 500) -> QualityReport:
    issues: List[QualityIssue] = []

    drugs = list(db.scalars(select(Drug).options(selectinload(Drug.products)).limit(limit)).all())
    products = list(db.scalars(
        select(Product).options(selectinload(Product.images), selectinload(Product.ingredients)).limit(limit)
    ).all())

    checked = 0
    for d in drugs:
        checked += 1
        label = d.generic_name_en or d.generic_name_ar or d.id
        if not d.generic_name_en and not d.generic_name_ar:
            issues.append(QualityIssue("missing_generic_name", "error", "drug", d.id, label, "Generic name is missing."))
        if not d.generic_name_ar:
            issues.append(QualityIssue("missing_arabic_translation", "warning", "drug", d.id, label, "Arabic name is missing."))
        if not d.mechanism_en:
            issues.append(QualityIssue("missing_mechanism", "info", "drug", d.id, label, "Mechanism of action is empty."))
        if d.verification_status != "verified":
            issues.append(QualityIssue("unverified_record", "warning", "drug", d.id, label,
                                       f"Record is not verified (status: {d.verification_status})."))
        if not d.search_text:
            issues.append(QualityIssue("missing_search_text", "warning", "drug", d.id, label, "Search index text is empty."))

    for p in products:
        checked += 1
        label = f"{p.brand_name_en} {p.strength}".strip() or p.id
        if not p.strength:
            issues.append(QualityIssue("missing_strength", "error", "product", p.id, label, "Strength is missing."))
        if not p.dosage_form:
            issues.append(QualityIssue("invalid_dosage_form", "error", "product", p.id, label, "Dosage form is missing/invalid."))
        if not p.manufacturer_id:
            issues.append(QualityIssue("missing_manufacturer", "warning", "product", p.id, label, "Manufacturer is missing."))
        if not p.barcode and not p.registration_number:
            issues.append(QualityIssue("invalid_barcode", "info", "product", p.id, label,
                                       "Neither barcode nor registration number is set."))
        if not p.images:
            issues.append(QualityIssue("missing_image", "info", "product", p.id, label, "Product has no images."))
        for img in p.images:
            if img.verification_status == "rejected":
                issues.append(QualityIssue("broken_image", "warning", "product", p.id, label,
                                           "A product image was rejected in review."))
        if p.verification_status != "verified":
            issues.append(QualityIssue("unverified_record", "warning", "product", p.id, label,
                                       f"Record is not verified (status: {p.verification_status})."))

    # duplicate check (same brand+strength+form)
    dup_keys: Dict[tuple, List[str]] = {}
    for p in products:
        key = ((p.brand_name_en or "").lower(), (p.strength or "").lower(), (p.dosage_form or "").lower())
        dup_keys.setdefault(key, []).append(p.id)
    for key, ids in dup_keys.items():
        if len(ids) > 1 and key[0]:
            for pid in ids:
                issues.append(QualityIssue("duplicate_product", "warning", "product", pid,
                                           f"{key[0]} {key[1]}", "Possible duplicate product (same brand/strength/form)."))

    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    total_findings = len(issues)
    denom = max(checked, 1)
    score = max(0.0, 100.0 - (errors * 5 + warnings * 2 + (total_findings - errors - warnings) * 0.5) / denom * 10)

    summary: Dict[str, int] = {}
    for issue in issues:
        summary[issue.code] = summary.get(issue.code, 0) + 1

    return QualityReport(
        total_records=checked,
        issues=issues,
        score=round(score, 1),
        summary=summary,
        metrics=collect_metrics(db),
    )
