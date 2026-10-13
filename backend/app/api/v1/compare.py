"""Drug comparison (§79–§81): side-by-side comparison of 2–4 drug records.

CRITICAL (§81): the comparison shows DIFFERENCES and EQUIVALENCES between
records only. It is NOT a therapeutic recommendation and NOT substitution
advice. "Equivalent Product" never means clinically interchangeable.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.services.rag import DISCLAIMER_AR, DISCLAIMER_EN
from app.core.errors import ValidationFailed
from app.models import (
    BodySystem,
    Drug,
    DrugDosage,
    DrugInteraction,
    DrugPregnancy,
    DrugSideEffect,
    DrugSource,
    DrugSynonym,
    ProductIngredient,
)

router = APIRouter(prefix="/drugs", tags=["drugs"])

MAX_COMPARE = 4


def _collect(db: Session, drug: Drug) -> dict:
    syn = list(db.scalars(select(DrugSynonym.term).where(DrugSynonym.drug_id == drug.id)).all())
    dosages = db.scalars(select(DrugDosage).where(DrugDosage.drug_id == drug.id)).all()
    preg = db.scalars(select(DrugPregnancy).where(DrugPregnancy.drug_id == drug.id)).all()
    inter = db.scalars(select(DrugInteraction).where(DrugInteraction.drug_id == drug.id)).all()
    effects = db.scalars(select(DrugSideEffect).where(DrugSideEffect.drug_id == drug.id)).all()
    source_count = db.scalar(
        select(func.count()).select_from(DrugSource).where(DrugSource.drug_id == drug.id)
    ) or 0
    product_ids = [p.id for p in drug.products]
    system_ids = [c.body_system_id for c in drug.classifications]
    systems = [
        {"code": s.slug, "name_en": s.name_en, "name_ar": s.name_ar}
        for s in db.scalars(select(BodySystem).where(BodySystem.id.in_(system_ids or [""]))).all()
    ]
    ingredients = []
    if product_ids:
        for row in db.execute(
            select(ProductIngredient.ingredient_name_en, ProductIngredient.strength, ProductIngredient.strength_unit)
            .where(ProductIngredient.product_id.in_(product_ids))
            .distinct()
        ).all():
            ingredients.append({"name": row[0], "strength": row[1], "unit": row[2]})
    return {
        "id": drug.id,
        "generic_name_en": drug.generic_name_en,
        "generic_name_ar": drug.generic_name_ar,
        "drug_class": drug.drug_class,
        "mechanism_en": drug.mechanism_en,
        "ingredients": ingredients,
        "synonyms": syn,
        "body_systems": systems,
        "dosages": [
            {"population": d.population, "route": d.route, "text_en": d.text_en, "is_verified": d.is_verified}
            for d in dosages
        ],
        "pregnancy": [
            {"risk_label": p.risk_label, "risk_system": p.risk_system, "text_en": p.text_en}
            for p in preg
        ],
        "interactions": [
            {"interacting_agent": i.interacting_agent, "severity": i.severity, "text_en": i.text_en}
            for i in inter
        ],
        "side_effects": [
            {"text_en": s.text_en, "frequency": s.frequency, "is_serious": s.is_serious}
            for s in effects
        ],
        "source_count": source_count,
        "products_count": len(drug.products),
        "verification_status": drug.verification_status,
        "record_version": drug.record_version,
        "is_demo": drug.is_demo,
    }


@router.get("/compare")
def compare_drugs(
    ids: List[str] = Query(..., min_length=2, max_length=MAX_COMPARE),
    db: Session = Depends(get_db),
) -> dict:
    """Side-by-side comparison (§79–§81). Public, like the drug pages."""
    unique = list(dict.fromkeys(ids))
    if len(unique) < 2:
        raise ValidationFailed("At least two distinct drug ids are required.")
    drugs = db.scalars(
        select(Drug)
        .options(selectinload(Drug.classifications), selectinload(Drug.products))
        .where(Drug.id.in_(unique))
    ).all()
    if len(drugs) < 2:
        raise ValidationFailed("At least two of the given drug ids must exist.")
    by_id = {d.id: d for d in drugs}
    ordered = [by_id[i] for i in unique if i in by_id]

    fields = [
        "generic_name_en", "generic_name_ar", "drug_class", "mechanism_en",
        "ingredients", "synonyms", "body_systems", "dosages", "pregnancy",
        "interactions", "side_effects", "source_count", "products_count",
        "verification_status", "is_demo",
    ]
    collected = [_collect(db, d) for d in ordered]
    rows = []
    for f in fields:
        values = [c[f] for c in collected]
        identical = all(v == values[0] for v in values)
        rows.append({"field": f, "values": values, "identical": identical})

    return {
        "drugs": [{"id": d.id, "label": d.generic_name_en or d.generic_name_ar or d.id} for d in ordered],
        "rows": rows,
        "notes": [
            "Comparison shows differences and equivalences between records only (§81).",
            "This is NOT a therapeutic recommendation and NOT substitution advice.",
            "'Equivalent Product' means product-record equivalence only — never clinical interchangeability.",
            "Verification status and DEMO markers are shown per column — trust only verified data.",
        ],
        "disclaimer_en": DISCLAIMER_EN,
        "disclaimer_ar": DISCLAIMER_AR,
    }
