"""Taxonomy endpoints: 18 body systems, groups, classes, dosage forms, routes,
countries, manufacturers, sources (§4, §8, §24)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import (
    BodySystem,
    Country,
    DosageForm,
    DrugClassification,
    Manufacturer,
    PharmacologicalClass,
    Product,
    Route,
    Source,
    TherapeuticGroup,
    User,
)
from app.schemas.common import Message
from app.schemas.taxonomy import (
    BodySystemOut,
    CountryOut,
    DosageFormOut,
    ManufacturerCreate,
    ManufacturerOut,
    PharmacologicalClassOut,
    RouteOut,
    SourceCreate,
    SourceOut,
    TaxonomyCreate,
    TherapeuticGroupOut,
)
from app.services.audit import record_audit

router = APIRouter(tags=["taxonomy"])


# ------------------------------------------------------------------ systems
@router.get("/systems", response_model=dict)
def list_systems(db: Session = Depends(get_db)) -> dict:
    systems = db.scalars(select(BodySystem).order_by(BodySystem.sort_order)).all()
    items = []
    for s in systems:
        drug_count = db.scalar(
            select(func.count()).select_from(DrugClassification).where(DrugClassification.body_system_id == s.id)
        ) or 0
        item = BodySystemOut.model_validate(s).model_dump()
        item["drug_count"] = drug_count
        items.append(item)
    return {"items": items, "total": len(items)}


@router.post("/systems", response_model=BodySystemOut,
             dependencies=[Depends(require_permission("settings.manage"))])
def create_system(payload: TaxonomyCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> BodySystemOut:
    system = BodySystem(
        name_en=payload.name_en, name_ar=payload.name_ar,
        slug=payload.slug or payload.name_en.lower().replace(" ", "-"),
        description_en=payload.description_en, description_ar=payload.description_ar,
        sort_order=payload.sort_order,
    )
    db.add(system)
    db.flush()
    return BodySystemOut.model_validate(system)


@router.get("/systems/{system_id}/groups", response_model=dict)
def system_groups(system_id: str, db: Session = Depends(get_db)) -> dict:
    groups = db.scalars(
        select(TherapeuticGroup).where(TherapeuticGroup.body_system_id == system_id).order_by(TherapeuticGroup.sort_order)
    ).all()
    result = []
    for g in groups:
        classes = db.scalars(
            select(PharmacologicalClass).where(PharmacologicalClass.therapeutic_group_id == g.id)
        ).all()
        item = TherapeuticGroupOut.model_validate(g).model_dump()
        item["pharmacological_classes"] = [PharmacologicalClassOut.model_validate(c).model_dump() for c in classes]
        result.append(item)
    return {"items": result, "total": len(result)}


@router.get("/therapeutic-groups", response_model=dict)
def list_therapeutic_groups(db: Session = Depends(get_db), body_system_id: Optional[str] = None) -> dict:
    stmt = select(TherapeuticGroup)
    if body_system_id:
        stmt = stmt.where(TherapeuticGroup.body_system_id == body_system_id)
    rows = db.scalars(stmt.order_by(TherapeuticGroup.sort_order)).all()
    return {"items": [TherapeuticGroupOut.model_validate(r).model_dump() for r in rows], "total": len(rows)}


@router.post("/therapeutic-groups", response_model=TherapeuticGroupOut,
             dependencies=[Depends(require_permission("settings.manage"))])
def create_therapeutic_group(payload: TaxonomyCreate, db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)) -> TherapeuticGroupOut:
    if not payload.body_system_id:
        raise NotFoundError("BodySystem")
    group = TherapeuticGroup(
        body_system_id=payload.body_system_id,
        name_en=payload.name_en, name_ar=payload.name_ar,
        slug=payload.slug or payload.name_en.lower().replace(" ", "-"),
        sort_order=payload.sort_order,
    )
    db.add(group)
    db.flush()
    return TherapeuticGroupOut.model_validate(group)


@router.get("/pharmacological-classes", response_model=dict)
def list_pharm_classes(db: Session = Depends(get_db),
                       therapeutic_group_id: Optional[str] = None) -> dict:
    stmt = select(PharmacologicalClass)
    if therapeutic_group_id:
        stmt = stmt.where(PharmacologicalClass.therapeutic_group_id == therapeutic_group_id)
    rows = db.scalars(stmt.order_by(PharmacologicalClass.sort_order)).all()
    return {"items": [PharmacologicalClassOut.model_validate(r).model_dump() for r in rows], "total": len(rows)}


@router.post("/pharmacological-classes", response_model=PharmacologicalClassOut,
             dependencies=[Depends(require_permission("settings.manage"))])
def create_pharm_class(payload: TaxonomyCreate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> PharmacologicalClassOut:
    if not payload.therapeutic_group_id:
        raise NotFoundError("TherapeuticGroup")
    cls = PharmacologicalClass(
        therapeutic_group_id=payload.therapeutic_group_id,
        name_en=payload.name_en, name_ar=payload.name_ar,
        slug=payload.slug or payload.name_en.lower().replace(" ", "-"),
        sort_order=payload.sort_order,
    )
    db.add(cls)
    db.flush()
    return PharmacologicalClassOut.model_validate(cls)


# ------------------------------------------------------------------ dosage forms / routes / countries
@router.get("/dosage-forms", response_model=dict)
def list_dosage_forms(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(DosageForm).order_by(DosageForm.name_en)).all()
    return {"items": [DosageFormOut.model_validate(r).model_dump() for r in rows], "total": len(rows)}


@router.post("/dosage-forms", response_model=DosageFormOut,
             dependencies=[Depends(require_permission("settings.manage"))])
def create_dosage_form(payload: TaxonomyCreate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> DosageFormOut:
    form = DosageForm(name_en=payload.name_en, name_ar=payload.name_ar,
                      slug=payload.slug or payload.name_en.lower().replace(" ", "_"))
    db.add(form)
    db.flush()
    return DosageFormOut.model_validate(form)


@router.get("/routes", response_model=dict)
def list_routes(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(Route).order_by(Route.name_en)).all()
    return {"items": [RouteOut.model_validate(r).model_dump() for r in rows], "total": len(rows)}


@router.get("/countries", response_model=dict)
def list_countries(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(Country).order_by(Country.name_en)).all()
    return {"items": [CountryOut.model_validate(r).model_dump() for r in rows], "total": len(rows)}


# ------------------------------------------------------------------ manufacturers
@router.get("/manufacturers", response_model=dict)
def list_manufacturers(db: Session = Depends(get_db), q: str = "",
                       page: int = 1, limit: int = 25) -> dict:
    stmt = select(Manufacturer)
    if q:
        stmt = stmt.where(Manufacturer.name_en.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Manufacturer.name_en).offset((page - 1) * limit).limit(limit)).all()
    return {
        "items": [ManufacturerOut.model_validate(r).model_dump() for r in rows],
        "total": total, "page": page, "limit": limit, "has_more": page * limit < total,
    }


@router.post("/manufacturers", response_model=ManufacturerOut,
             dependencies=[Depends(require_permission("product.edit"))])
def create_manufacturer(payload: ManufacturerCreate, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)) -> ManufacturerOut:
    m = Manufacturer(**payload.model_dump())
    db.add(m)
    db.flush()
    return ManufacturerOut.model_validate(m)


# ------------------------------------------------------------------ sources (§24)
@router.get("/sources", response_model=dict)
def list_sources(db: Session = Depends(get_db), page: int = 1, limit: int = 25) -> dict:
    total = db.scalar(select(func.count()).select_from(Source)) or 0
    rows = db.scalars(select(Source).order_by(Source.name).offset((page - 1) * limit).limit(limit)).all()
    return {
        "items": [SourceOut.model_validate(r).model_dump() for r in rows],
        "total": total, "page": page, "limit": limit, "has_more": page * limit < total,
    }


@router.post("/sources", response_model=SourceOut,
             dependencies=[Depends(require_permission("source.manage"))])
def create_source(payload: SourceCreate, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> SourceOut:
    src = Source(**payload.model_dump())
    db.add(src)
    db.flush()
    record_audit(db, action="source.created", entity_type="source", entity_id=src.id, user_id=user.id,
                 new_value=payload.name)
    db.flush()
    return SourceOut.model_validate(src)
