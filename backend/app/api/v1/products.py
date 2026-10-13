"""Product (commercial) endpoints (§7, §15)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.errors import NotFoundError, ValidationFailed
from app.db.session import get_db
from app.models import (
    Manufacturer,
    Product,
    ProductImage,
    ProductIngredient,
    ProductPackage,
    ProductSource,
    Source,
    User,
    VerificationStatus,
)
from app.schemas.common import Message, VerificationRecordOut, VerificationTransition
from app.schemas.product import ProductCreate, ProductDetailOut, ProductOut, ProductUpdate
from app.services import verification
from app.services.audit import record_audit
from app.services.duplicates import find_product_duplicates
from app.services.search import build_product_search_fields
from app.services.storage import store_product_image

router = APIRouter(prefix="/products", tags=["products"])


def _get_product(db: Session, product_id: str) -> Product:
    p = db.get(Product, product_id)
    if p is None:
        raise NotFoundError("Product", product_id)
    return p


@router.get("", response_model=dict)
def list_products(
    db: Session = Depends(get_db),
    q: str = "",
    drug_id: Optional[str] = None,
    dosage_form: Optional[str] = None,
    manufacturer_id: Optional[str] = None,
    verification_status: Optional[str] = None,
    include_demo: bool = True,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
) -> dict:
    stmt = select(Product)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Product.brand_name_en.ilike(like) | Product.brand_name_ar.ilike(like)
                          | Product.barcode.ilike(like) | Product.search_text.like(like.lower()))
    if drug_id:
        stmt = stmt.where(Product.drug_id == drug_id)
    if dosage_form:
        stmt = stmt.where(Product.dosage_form == dosage_form)
    if manufacturer_id:
        stmt = stmt.where(Product.manufacturer_id == manufacturer_id)
    if verification_status:
        stmt = stmt.where(Product.verification_status == verification_status)
    if not include_demo:
        stmt = stmt.where(Product.is_demo.is_(False))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Product.updated_at.desc())
    rows = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
    return {
        "items": [ProductOut.model_validate(r).model_dump() for r in rows],
        "total": total, "page": page, "limit": limit,
        "has_more": page * limit < total,
    }


@router.post("", response_model=ProductOut, dependencies=[Depends(require_permission("product.create"))])
def create_product(payload: ProductCreate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> ProductOut:
    data = payload.model_dump(exclude={"ingredients", "manufacturer_name"})
    product = Product(**data)
    product.verification_status = VerificationStatus.DRAFT.value
    product.created_by = user.id
    product.updated_by = user.id

    if payload.manufacturer_name and not payload.manufacturer_id:
        manu = Manufacturer(name_en=payload.manufacturer_name)
        db.add(manu)
        db.flush()
        product.manufacturer_id = manu.id

    db.add(product)
    db.flush()

    for ing in payload.ingredients:
        db.add(ProductIngredient(product_id=product.id, **ing.model_dump()))
    db.flush()
    build_product_search_fields(product)

    record_audit(db, action="product.created", entity_type="product", entity_id=product.id,
                 user_id=user.id, new_value=payload.brand_name_en,
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return ProductOut.model_validate(product)


@router.get("/{product_id}", response_model=ProductDetailOut)
def get_product(product_id: str, db: Session = Depends(get_db)) -> ProductDetailOut:
    p = _get_product(db, product_id)
    out = ProductOut.model_validate(p).model_dump()
    out.update({
        "strength_value": p.strength_value, "strength_unit": p.strength_unit, "gtin": p.gtin,
        "manufacturer_id": p.manufacturer_id,
        "manufacturer_name": p.manufacturer.name_en if p.manufacturer else None,
        "manufacturer_country_id": p.manufacturer_country_id,
        "marketing_country_id": p.marketing_country_id,
        "ingredients": [{
            "ingredient_name_en": i.ingredient_name_en, "ingredient_name_ar": i.ingredient_name_ar,
            "drug_id": i.drug_id, "strength": i.strength, "is_primary": i.is_primary,
        } for i in p.ingredients],
        "packages": [{
            "id": pk.id, "package_size": pk.package_size,
            "package_description": pk.package_description, "barcode": pk.barcode, "gtin": pk.gtin,
        } for pk in p.packages],
        "images": [{
            "id": img.id, "kind": img.kind, "storage_path": img.storage_path,
            "thumbnail_path": img.thumbnail_path, "file_type": img.file_type,
            "width": img.width, "height": img.height, "verification_status": img.verification_status,
        } for img in p.images],
        "sources": [],
        "drug": {"id": p.drug.id, "generic_name_en": p.drug.generic_name_en,
                 "generic_name_ar": p.drug.generic_name_ar,
                 "verification_status": p.drug.verification_status} if p.drug else None,
    })
    for link in db.scalars(select(ProductSource).where(ProductSource.product_id == p.id)).all():
        src = db.get(Source, link.source_id)
        if src:
            out["sources"].append({"id": src.id, "name": src.name, "url": src.url,
                                   "section": link.section, "source_type": src.source_type})
    return ProductDetailOut(**out)


@router.patch("/{product_id}", response_model=ProductOut, dependencies=[Depends(require_permission("product.edit"))])
def update_product(product_id: str, payload: ProductUpdate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> ProductOut:
    p = _get_product(db, product_id)
    before = {k: getattr(p, k) for k in payload.model_fields_set if hasattr(p, k)}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(p, key, value)
    p.updated_by = user.id
    p.record_version = (p.record_version or 1) + 1
    build_product_search_fields(p)
    record_audit(db, action="product.updated", entity_type="product", entity_id=p.id, user_id=user.id,
                 previous_value=before, new_value=payload.model_dump(exclude_unset=True),
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return ProductOut.model_validate(p)


@router.get("/{product_id}/duplicates", response_model=dict,
            dependencies=[Depends(require_permission("product.edit"))])
def product_duplicates(product_id: str, db: Session = Depends(get_db)) -> dict:
    p = _get_product(db, product_id)
    matches = find_product_duplicates(
        db,
        brand_name_en=p.brand_name_en,
        brand_name_ar=p.brand_name_ar,
        strength=p.strength,
        dosage_form=p.dosage_form,
        manufacturer_name=p.manufacturer.name_en if p.manufacturer else "",
        barcode=p.barcode,
        registration_number=p.registration_number,
        exclude_product_id=p.id,
    )
    return {
        "note": "Possible duplicates require human review — records are never auto-merged.",
        "matches": [{
            "kind": m.kind, "product_id": m.product_id, "product_label": m.product_label,
            "reasons": m.reasons, "confidence": m.confidence,
        } for m in matches],
    }


@router.post("/{product_id}/packages", response_model=Message,
             dependencies=[Depends(require_permission("product.edit"))])
def add_package(product_id: str, package_size: str = Form(""), package_description: str = Form(""),
                barcode: str = Form(""), db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> Message:
    p = _get_product(db, product_id)
    db.add(ProductPackage(product_id=p.id, package_size=package_size,
                          package_description=package_description, barcode=barcode))
    db.flush()
    return Message(message="Package added.")


@router.post("/{product_id}/images", response_model=Message,
             dependencies=[Depends(require_permission("image.upload"))])
async def upload_image(product_id: str, request: Request, file: UploadFile = File(...),
                       kind: str = Form("front_package"),
                       source: str = Form(""), copyright_info: str = Form(""),
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Message:
    p = _get_product(db, product_id)
    content = await file.read()
    try:
        stored = store_product_image(content, file.filename or "upload", kind)
    except ValidationFailed:
        raise
    except Exception:
        raise ValidationFailed("Image could not be processed.")
    db.add(ProductImage(
        product_id=p.id,
        kind=kind,
        storage_path=stored.storage_path,
        file_type=stored.file_type,
        file_size=stored.file_size,
        width=stored.width,
        height=stored.height,
        thumbnail_path=stored.thumbnail_path,
        source=source,
        copyright_info=copyright_info,
        uploaded_by=user.id,
        verification_status=VerificationStatus.PENDING_VERIFICATION.value,
    ))
    record_audit(db, action="image.uploaded", entity_type="product", entity_id=p.id,
                 user_id=user.id, new_value=stored.original_name,
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return Message(message="Image uploaded and queued for review.")


@router.post("/{product_id}/verify", response_model=VerificationRecordOut,
             dependencies=[Depends(require_permission("product.verify"))])
def verify_product(product_id: str, payload: VerificationTransition, request: Request,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> VerificationRecordOut:
    record = verification.transition(
        db, entity_type="product", entity_id=product_id,
        new_status=payload.new_status, reviewer_id=user.id, notes=payload.notes,
        ip_address=request.client.host if request.client else "",
    )
    return VerificationRecordOut.model_validate(record)
