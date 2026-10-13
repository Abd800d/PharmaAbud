"""Duplicate detection for imports and product management (§21).

Levels: EXACT / POSSIBLE / POTENTIAL. Uncertain records are NEVER merged
automatically — a human review interface decides (§21).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Product
from app.services.normalization import (
    name_key,
    normalize_manufacturer,
    normalize_strength,
    normalize_text,
)


@dataclass
class DuplicateMatch:
    kind: str                 # exact | possible | potential
    product_id: str
    product_label: str
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0


def find_product_duplicates(
    db: Session,
    *,
    brand_name_en: str = "",
    brand_name_ar: str = "",
    strength: str = "",
    dosage_form: str = "",
    manufacturer_name: str = "",
    country: str = "",
    barcode: str = "",
    registration_number: str = "",
    exclude_product_id: Optional[str] = None,
) -> List[DuplicateMatch]:
    matches: List[DuplicateMatch] = []

    # --- EXACT: barcode or registration number identity ---
    if barcode or registration_number:
        stmt = select(Product).where(or_(
            Product.barcode == barcode,
            Product.registration_number == registration_number,
        ))
        if exclude_product_id:
            stmt = stmt.where(Product.id != exclude_product_id)
        for p in db.scalars(stmt.limit(20)).all():
            reasons = []
            if barcode and p.barcode == barcode:
                reasons.append("barcode")
            if registration_number and p.registration_number == registration_number:
                reasons.append("registration_number")
            matches.append(DuplicateMatch("exact", p.id, _label(p), reasons, 1.0))

    if any(m.kind == "exact" for m in matches):
        return matches

    # --- candidate pool by name similarity ---
    key = name_key(brand_name_en or brand_name_ar)
    if not key:
        return matches
    like = f"%{key[:8]}%"
    stmt = select(Product).options(selectinload(Product.manufacturer)).where(
        or_(Product.search_text.like(like), Product.brand_name_en.ilike(f"%{(brand_name_en or '')[:8]}%"))
    )
    if exclude_product_id:
        stmt = stmt.where(Product.id != exclude_product_id)
    candidates = list(db.scalars(stmt.limit(100)).all())

    ns = normalize_strength(strength)
    form = normalize_text(dosage_form)
    manu = normalize_manufacturer(manufacturer_name)

    for p in candidates:
        reasons: List[str] = []
        score = 0.0

        same_brand = name_key(p.brand_name_en) == key or (brand_name_ar and name_key(p.brand_name_ar) == name_key(brand_name_ar))
        if same_brand:
            reasons.append("brand_name")
            score += 0.4

        ps = normalize_strength(p.strength)
        same_strength = bool(ns.valid and ps.valid and abs((ns.canonical_mg or ns.value or 0) - (ps.canonical_mg or ps.value or 0)) < 1e-9 and ns.unit == ps.unit)
        if same_strength:
            reasons.append("strength")
            score += 0.2

        if form and normalize_text(p.dosage_form) == form:
            reasons.append("dosage_form")
            score += 0.15

        p_manu = normalize_manufacturer(p.manufacturer.name_en if p.manufacturer else "")
        same_manu = bool(manu and p_manu and (manu in p_manu or p_manu in manu))
        if same_manu:
            reasons.append("manufacturer")
            score += 0.15

        if country and p.manufacturer_country_id:
            score += 0.05

        if same_brand and same_strength and (form and normalize_text(p.dosage_form) == form) and same_manu:
            matches.append(DuplicateMatch("possible", p.id, _label(p), reasons, min(score, 0.99)))
        elif same_brand and (same_strength or same_manu):
            matches.append(DuplicateMatch("potential", p.id, _label(p), reasons, min(score, 0.9)))
        elif same_brand:
            matches.append(DuplicateMatch("potential", p.id, _label(p), reasons, min(score, 0.7)))

    matches.sort(key=lambda m: -m.confidence)
    return matches


def _label(p: Product) -> str:
    manu = p.manufacturer.name_en if p.manufacturer else ""
    return f"{p.brand_name_en} | {p.strength} | {p.dosage_form} | {manu}".strip(" |")
