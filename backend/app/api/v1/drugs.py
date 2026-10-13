"""Drug encyclopedia endpoints (§6, §14, §89)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_optional_user, get_current_user, require_permission
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import (
    ContentSource,
    Drug,
    DrugAlternative,
    DrugClassification,
    DrugContraindication,
    DrugDosage,
    DrugFoodInteraction,
    DrugIndication,
    DrugInteraction,
    DrugLactation,
    DrugMonitoring,
    DrugAdministration,
    DrugOverdose,
    DrugPregnancy,
    DrugPrecaution,
    DrugSideEffect,
    DrugSynonym,
    DrugWarning,
    Product,
    Source,
    User,
    VerificationStatus,
)
from app.schemas.common import Message, VerificationRecordOut, VerificationTransition
from app.schemas.drug import DosageIn, DrugCreate, DrugDetailOut, DrugOut, DrugSynonymIn, DrugUpdate
from app.services import verification
from app.services.audit import record_audit
from app.services.search import build_drug_search_fields, equivalent_products

router = APIRouter(prefix="/drugs", tags=["drugs"])


def _get_drug(db: Session, drug_id: str) -> Drug:
    drug = db.get(Drug, drug_id)
    if drug is None:
        raise NotFoundError("Drug", drug_id)
    return drug


@router.get("", response_model=dict)
def list_drugs(
    db: Session = Depends(get_db),
    q: str = "",
    system_id: Optional[str] = None,
    verification_status: Optional[str] = None,
    include_demo: bool = True,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    sort: str = Query("updated", pattern="^(updated|name|created)$"),
) -> dict:
    stmt = select(Drug)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Drug.generic_name_en.ilike(like) | Drug.generic_name_ar.ilike(like) | Drug.atc_code.ilike(like))
    if system_id:
        stmt = stmt.where(Drug.id.in_(select(DrugClassification.drug_id).where(DrugClassification.body_system_id == system_id)))
    if verification_status:
        stmt = stmt.where(Drug.verification_status == verification_status)
    if not include_demo:
        stmt = stmt.where(Drug.is_demo.is_(False))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if sort == "name":
        stmt = stmt.order_by(Drug.generic_name_en)
    elif sort == "created":
        stmt = stmt.order_by(Drug.created_at.desc())
    else:
        stmt = stmt.order_by(Drug.updated_at.desc())
    rows = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
    return {
        "items": [DrugOut.model_validate(r).model_dump() for r in rows],
        "total": total, "page": page, "limit": limit,
        "has_more": page * limit < total,
    }


@router.post("", response_model=DrugOut, dependencies=[Depends(require_permission("drug.create"))])
def create_drug(payload: DrugCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> DrugOut:
    drug = Drug(**payload.model_dump())
    drug.created_by = user.id
    drug.updated_by = user.id
    drug.verification_status = VerificationStatus.DRAFT.value
    db.add(drug)
    db.flush()
    build_drug_search_fields(db, drug)
    record_audit(db, action="drug.created", entity_type="drug", entity_id=drug.id, user_id=user.id,
                 new_value=payload.generic_name_en,
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return DrugOut.model_validate(drug)


@router.get("/{drug_id}", response_model=DrugDetailOut)
def get_drug(drug_id: str, db: Session = Depends(get_db)) -> DrugDetailOut:
    drug = _get_drug(db, drug_id)
    data = DrugOut.model_validate(drug).model_dump()
    detail = {
        **data,
        "overview_en": drug.overview_en, "overview_ar": drug.overview_ar,
        "mechanism_en": drug.mechanism_en, "mechanism_ar": drug.mechanism_ar,
        "pharmacodynamics_en": drug.pharmacodynamics_en, "pharmacodynamics_ar": drug.pharmacodynamics_ar,
        "pharmacokinetics_en": drug.pharmacokinetics_en, "pharmacokinetics_ar": drug.pharmacokinetics_ar,
        "half_life": drug.half_life,
        "synonyms": [{"term": s.term, "language": s.language} for s in drug.synonyms],
        "indications": [{"text_en": x.text_en, "text_ar": x.text_ar, "is_off_label": x.is_off_label}
                        for x in db.scalars(select(DrugIndication).where(DrugIndication.drug_id == drug.id)).all()],
        "contraindications": [{"text_en": x.text_en, "text_ar": x.text_ar, "severity": x.severity}
                              for x in db.scalars(select(DrugContraindication).where(DrugContraindication.drug_id == drug.id)).all()],
        "warnings": [{"text_en": x.text_en, "text_ar": x.text_ar, "severity": x.severity}
                     for x in db.scalars(select(DrugWarning).where(DrugWarning.drug_id == drug.id)).all()],
        "precautions": [{"text_en": x.text_en, "text_ar": x.text_ar}
                        for x in db.scalars(select(DrugPrecaution).where(DrugPrecaution.drug_id == drug.id)).all()],
        "side_effects": [{"text_en": x.text_en, "text_ar": x.text_ar, "frequency": x.frequency, "is_serious": x.is_serious}
                         for x in db.scalars(select(DrugSideEffect).where(DrugSideEffect.drug_id == drug.id)).all()],
        "interactions": [{"interacting_agent": x.interacting_agent, "text_en": x.text_en, "text_ar": x.text_ar, "severity": x.severity}
                         for x in db.scalars(select(DrugInteraction).where(DrugInteraction.drug_id == drug.id)).all()],
        "food_interactions": [{"text_en": x.text_en, "text_ar": x.text_ar}
                              for x in db.scalars(select(DrugFoodInteraction).where(DrugFoodInteraction.drug_id == drug.id)).all()],
        "dosages": [{"population": x.population, "indication": x.indication, "route": x.route,
                     "text_en": x.text_en, "text_ar": x.text_ar, "dose_value": x.dose_value,
                     "dose_unit": x.dose_unit, "frequency": x.frequency, "max_dose": x.max_dose,
                     "duration": x.duration, "is_verified": x.is_verified}
                    for x in db.scalars(select(DrugDosage).where(DrugDosage.drug_id == drug.id)).all()],
        "pregnancy": None,
        "lactation": None,
        "overdose": None,
        "monitoring": [{"text_en": x.text_en, "text_ar": x.text_ar}
                       for x in db.scalars(select(DrugMonitoring).where(DrugMonitoring.drug_id == drug.id)).all()],
        "administration": [{"text_en": x.text_en, "text_ar": x.text_ar}
                           for x in db.scalars(select(DrugAdministration).where(DrugAdministration.drug_id == drug.id)).all()],
        "classifications": [
            {"pharmacological_class_id": c.pharmacological_class_id,
             "therapeutic_group_id": c.therapeutic_group_id,
             "body_system_id": c.body_system_id,
             "is_primary": c.is_primary}
            for c in drug.classifications
        ],
        "sources": [],
    }
    preg = db.scalars(select(DrugPregnancy).where(DrugPregnancy.drug_id == drug.id)).first()
    if preg:
        detail["pregnancy"] = {"text_en": preg.text_en, "text_ar": preg.text_ar,
                               "risk_label": preg.risk_label, "risk_system": preg.risk_system,
                               "source_id": preg.source_id, "last_verified_date": preg.last_verified_date}
    lact = db.scalars(select(DrugLactation).where(DrugLactation.drug_id == drug.id)).first()
    if lact:
        detail["lactation"] = {"text_en": lact.text_en, "text_ar": lact.text_ar,
                               "milk_transfer": lact.milk_transfer,
                               "infant_considerations": lact.infant_considerations}
    od = db.scalars(select(DrugOverdose).where(DrugOverdose.drug_id == drug.id)).first()
    if od:
        detail["overdose"] = {"text_en": od.text_en, "text_ar": od.text_ar}

    from app.models import DrugSource

    for link in db.scalars(select(DrugSource).where(DrugSource.drug_id == drug.id)).all():
        src = db.get(Source, link.source_id)
        if src:
            detail["sources"].append({"id": src.id, "name": src.name, "url": src.url,
                                      "section": link.section, "source_type": src.source_type,
                                      "retrieved_date": src.retrieved_date})
    return DrugDetailOut(**detail)


@router.patch("/{drug_id}", response_model=DrugOut, dependencies=[Depends(require_permission("drug.edit"))])
def update_drug(drug_id: str, payload: DrugUpdate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> DrugOut:
    drug = _get_drug(db, drug_id)
    before = {k: getattr(drug, k) for k in payload.model_fields_set if hasattr(drug, k)}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(drug, key, value)
    drug.updated_by = user.id
    drug.record_version = (drug.record_version or 1) + 1
    build_drug_search_fields(db, drug)
    record_audit(db, action="drug.updated", entity_type="drug", entity_id=drug.id, user_id=user.id,
                 previous_value=before, new_value=payload.model_dump(exclude_unset=True),
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return DrugOut.model_validate(drug)


@router.delete("/{drug_id}", response_model=Message, dependencies=[Depends(require_permission("drug.delete"))])
def archive_drug(drug_id: str, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> Message:
    drug = _get_drug(db, drug_id)
    drug.verification_status = VerificationStatus.ARCHIVED.value
    record_audit(db, action="drug.archived", entity_type="drug", entity_id=drug.id, user_id=user.id)
    db.flush()
    return Message(message="Drug archived.")


@router.put("/{drug_id}/synonyms", response_model=DrugOut, dependencies=[Depends(require_permission("drug.edit"))])
def set_synonyms(drug_id: str, synonyms: List[DrugSynonymIn], db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> DrugOut:
    drug = _get_drug(db, drug_id)
    for s in list(drug.synonyms):
        db.delete(s)
    db.flush()
    for s in synonyms:
        db.add(DrugSynonym(drug_id=drug.id, term=s.term, language=s.language))
    db.flush()
    build_drug_search_fields(db, drug)
    db.flush()
    return DrugOut.model_validate(drug)


@router.post("/{drug_id}/dosages", response_model=Message, dependencies=[Depends(require_permission("drug.edit"))])
def add_dosage(drug_id: str, payload: DosageIn, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)) -> Message:
    drug = _get_drug(db, drug_id)
    db.add(DrugDosage(drug_id=drug.id, **payload.model_dump()))
    db.flush()
    return Message(message="Dosage entry added.")


@router.get("/{drug_id}/products", response_model=dict)
def drug_products(drug_id: str, db: Session = Depends(get_db),
                  strength: Optional[str] = None, dosage_form: Optional[str] = None,
                  route: Optional[str] = None) -> dict:
    _get_drug(db, drug_id)
    products = equivalent_products(db, drug_id, strength=strength, dosage_form=dosage_form, route=route)
    return {
        "label": "Equivalent Product",
        "note": "Same active ingredient. Not automatically a therapeutic alternative.",
        "items": [{
            "id": p.id, "brand_name_en": p.brand_name_en, "brand_name_ar": p.brand_name_ar,
            "strength": p.strength, "dosage_form": p.dosage_form, "route": p.route,
            "manufacturer": p.manufacturer.name_en if p.manufacturer else "",
            "verification_status": p.verification_status, "is_demo": p.is_demo,
        } for p in products],
    }


@router.get("/{drug_id}/alternatives", response_model=dict)
def drug_alternatives(drug_id: str, db: Session = Depends(get_db)) -> dict:
    _get_drug(db, drug_id)
    rows = db.scalars(select(DrugAlternative).where(DrugAlternative.drug_id == drug_id)).all()
    items = []
    for alt in rows:
        d = db.get(Drug, alt.alternative_drug_id)
        if d:
            items.append({
                "id": d.id, "generic_name_en": d.generic_name_en, "generic_name_ar": d.generic_name_ar,
                "rationale_en": alt.rationale_en, "rationale_ar": alt.rationale_ar,
                "evidence_level": alt.evidence_level,
            })
    return {
        "label": "Therapeutic Alternative",
        "note": "Different active ingredient that may be used for similar clinical purposes. "
                "Not a substitution recommendation — consult official product information.",
        "items": items,
    }


@router.post("/{drug_id}/verify", response_model=VerificationRecordOut,
             dependencies=[Depends(require_permission("drug.verify"))])
def verify_drug(drug_id: str, payload: VerificationTransition, request: Request,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> VerificationRecordOut:
    record = verification.transition(
        db, entity_type="drug", entity_id=drug_id,
        new_status=payload.new_status, reviewer_id=user.id,
        notes=payload.notes,
        ip_address=request.client.host if request.client else "",
    )
    return VerificationRecordOut.model_validate(record)


@router.get("/{drug_id}/verification-history", response_model=List[VerificationRecordOut])
def verification_history(drug_id: str, db: Session = Depends(get_db)) -> List[VerificationRecordOut]:
    return [VerificationRecordOut.model_validate(r) for r in verification.history(db, "drug", drug_id)]
