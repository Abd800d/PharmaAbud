"""Admin dashboard, review queues, data quality, exports (§26–§27, §57, §82)."""
from __future__ import annotations

import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_any_permission, require_permission
from app.core.errors import ForbiddenError
from app.db.session import get_db
from app.models import (
    BodySystem,
    Country,
    Drug,
    DrugClassification,
    Import,
    Manufacturer,
    Product,
    ProductImage,
    SearchTermStat,
    Source,
    User,
    VerificationRecord,
)
from app.schemas.common import Message
from app.services.audit import record_audit
from app.services.quality import run_quality_checks

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", dependencies=[Depends(require_any_permission("drug.read", "settings.manage", "user.manage"))])
def dashboard(db: Session = Depends(get_db)) -> dict:
    total_drugs = db.scalar(select(func.count()).select_from(Drug)) or 0
    total_products = db.scalar(select(func.count()).select_from(Product)) or 0
    verified_products = db.scalar(
        select(func.count()).select_from(Product).where(Product.verification_status == "verified")
    ) or 0
    pending_reviews = (
        db.scalar(select(func.count()).select_from(Product).where(Product.verification_status == "imported_pending_review")) or 0
    ) + (
        db.scalar(select(func.count()).select_from(Drug).where(Drug.verification_status == "imported_pending_review")) or 0
    )
    total_manufacturers = db.scalar(select(func.count()).select_from(Manufacturer)) or 0
    total_countries = db.scalar(select(func.count()).select_from(Country)) or 0
    total_images = db.scalar(select(func.count()).select_from(ProductImage)) or 0
    total_sources = db.scalar(select(func.count()).select_from(Source)) or 0
    failed_imports = db.scalar(select(func.count()).select_from(Import).where(Import.status == "failed")) or 0

    # charts: products by system
    by_system = []
    for s in db.scalars(select(BodySystem).order_by(BodySystem.sort_order)).all():
        count = db.scalar(
            select(func.count()).select_from(DrugClassification).where(DrugClassification.body_system_id == s.id)
        ) or 0
        by_system.append({"system": s.name_en, "system_ar": s.name_ar, "count": count})

    # verification status distribution
    verif_rows = db.execute(
        select(Product.verification_status, func.count()).group_by(Product.verification_status)
    ).all()
    verification_chart = [{"status": r[0], "count": r[1]} for r in verif_rows]

    # recent imports
    recent_imports = [
        {"id": i.id, "filename": i.filename, "status": i.status,
         "total_rows": i.total_rows, "imported_rows": i.imported_rows,
         "created_at": i.created_at.isoformat()}
        for i in db.scalars(select(Import).order_by(Import.created_at.desc()).limit(5)).all()
    ]

    return {
        "totals": {
            "drugs": total_drugs,
            "products": total_products,
            "verified_products": verified_products,
            "pending_reviews": pending_reviews,
            "manufacturers": total_manufacturers,
            "countries": total_countries,
            "images": total_images,
            "sources": total_sources,
            "failed_imports": failed_imports,
        },
        "charts": {
            "products_by_system": by_system,
            "verification_status": verification_chart,
        },
        "recent_imports": recent_imports,
    }


@router.get("/queues/review", dependencies=[Depends(require_any_permission("drug.verify", "product.verify"))])
def review_queue(db: Session = Depends(get_db), limit: int = Query(50, le=200)) -> dict:
    """Pharmacist review dashboard (§93)."""
    def pack(row, label_field):
        return {
            "id": row.id, "label": getattr(row, label_field),
            "verification_status": row.verification_status,
            "updated_at": row.updated_at.isoformat(), "is_demo": row.is_demo,
        }

    pending = db.scalars(
        select(Product).where(Product.verification_status == "imported_pending_review").limit(limit)
    ).all()
    pending_drugs = db.scalars(
        select(Drug).where(Drug.verification_status == "imported_pending_review").limit(limit)
    ).all()
    needs_update = db.scalars(
        select(Drug).where(Drug.verification_status == "needs_update").limit(limit)
    ).all()
    return {
        "pending_products": [pack(p, "brand_name_en") for p in pending],
        "pending_drugs": [pack(d, "generic_name_en") for d in pending_drugs],
        "needs_update": [pack(d, "generic_name_en") for d in needs_update],
    }


@router.get("/quality", dependencies=[Depends(require_any_permission("settings.manage", "drug.edit", "product.edit"))])
def data_quality(db: Session = Depends(get_db)) -> dict:
    report = run_quality_checks(db)
    return {
        "score": report.score,
        "score_note": "Data completeness indicator only — NOT a medical reliability score (§57).",
        "total_records": report.total_records,
        "metrics": report.metrics,
        "summary": report.summary,
        "issues": [{
            "code": i.code, "severity": i.severity, "entity_type": i.entity_type,
            "entity_id": i.entity_id, "entity_label": i.entity_label, "message": i.message,
        } for i in report.issues],
    }


@router.get("/search-analytics", dependencies=[Depends(require_permission("settings.manage"))])
def search_analytics(db: Session = Depends(get_db), limit: int = 20) -> dict:
    """Privacy-conscious aggregates only (§67) — no individual search histories."""
    top = db.scalars(select(SearchTermStat).order_by(SearchTermStat.hits.desc()).limit(limit)).all()
    zero = db.scalars(
        select(SearchTermStat).where(SearchTermStat.zero_results > 0).order_by(SearchTermStat.zero_results.desc()).limit(limit)
    ).all()
    return {
        "most_searched": [{"term": s.term, "hits": s.hits, "language": s.language} for s in top],
        "zero_result_terms": [{"term": s.term, "zero_results": s.zero_results} for s in zero],
        "note": "Aggregated statistics only. Individual users' searches are not exposed.",
    }


@router.get("/export", dependencies=[Depends(require_permission("data.export"))])
def export_data(
    request: Request,
    entity: str = Query("products", pattern="^(drugs|products)$"),
    format: str = Query("csv", pattern="^(csv|json)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Authorized bulk export — large exports are audit-logged (§82)."""
    if entity == "drugs":
        rows = db.scalars(select(Drug).limit(50000)).all()
        records = [{
            "id": d.id, "generic_name_en": d.generic_name_en, "generic_name_ar": d.generic_name_ar,
            "atc_code": d.atc_code, "verification_status": d.verification_status,
            "is_demo": d.is_demo,
        } for d in rows]
    else:
        rows = db.scalars(select(Product).limit(50000)).all()
        records = [{
            "id": p.id, "brand_name_en": p.brand_name_en, "brand_name_ar": p.brand_name_ar,
            "strength": p.strength, "dosage_form": p.dosage_form, "barcode": p.barcode,
            "verification_status": p.verification_status, "is_demo": p.is_demo,
        } for p in rows]

    record_audit(db, action="data.exported", entity_type=entity, user_id=user.id,
                 new_value=f"format={format},rows={len(records)}",
                 ip_address=request.client.host if request.client else "")
    db.flush()

    if format == "json":
        return Response(
            json.dumps({"entity": entity, "count": len(records), "items": records},
                       ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="aph_{entity}.json"'},
        )
    buf = io.StringIO()
    if records:
        writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    return PlainTextResponse(
        buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="aph_{entity}.csv"'},
    )


@router.post("/backup", response_model=Message, dependencies=[Depends(require_permission("settings.manage"))])
def trigger_backup(request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> Message:
    """Backup trigger. Production runs pg_dump via the ops scheduler (§60);
    this endpoint records the request and audit entry."""
    record_audit(db, action="backup.requested", entity_type="system", user_id=user.id,
                 ip_address=request.client.host if request.client else "")
    db.flush()
    return Message(message="Backup requested. Automated backups run on the deployment schedule (see DEPLOYMENT.md).")
