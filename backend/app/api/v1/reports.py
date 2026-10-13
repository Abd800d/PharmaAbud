"""Reports module (§96): data-quality and workflow reports + CSV export.

Reports included (§96):
  review-queue, source-coverage, duplicate-candidates, quality-by-drug,
  task-completion, drugs-needing-update, drugs-without-sources, unverified-fields.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_any_permission
from app.db.session import get_db
from app.core.errors import ForbiddenError
from app.models import (
    Drug,
    DrugDosage,
    DrugInteraction,
    DrugPregnancy,
    DrugSource,
    Import,
    ImportRow,
    Product,
    User,
)

router = APIRouter(prefix="/reports", tags=["reports"])

_READ = require_any_permission("drug.read", "product.read", "settings.manage")

REPORTS = [
    ("review-queue", "Review Queue Report", "Pending drugs/products awaiting pharmacist review (§96)."),
    ("source-coverage", "Source Coverage Report", "Drugs with/without registered sources (§96)."),
    ("duplicate-candidates", "Duplicate Candidates Report", "Exact/Possible/Potential duplicates awaiting human decision (§16)."),
    ("quality-by-drug", "Quality Report by Drug", "Per-drug missing-field breakdown (§96)."),
    ("task-completion", "Task Completion Report", "Import batches with completion percentage (§96)."),
    ("drugs-needing-update", "Drugs Needing Update Report", "Records flagged needs_update (§96)."),
    ("drugs-without-sources", "Drugs Without Sources Report", "Records with zero linked sources (§96)."),
    ("unverified-fields", "Unverified Fields Report", "Unverified records and empty critical sections (§96)."),
]


# ------------------------------------------------------------------ helpers
def _drug_label(d: Drug) -> str:
    return d.generic_name_en or d.generic_name_ar or d.id


def _coverage_rows(db: Session) -> list[dict]:
    counts = dict(
        db.execute(
            select(DrugSource.drug_id, func.count()).group_by(DrugSource.drug_id)
        ).all()
    )
    rows = []
    for d in db.scalars(select(Drug).order_by(Drug.generic_name_en)).all():
        rows.append({
            "id": d.id, "label": _drug_label(d),
            "verification_status": d.verification_status,
            "is_demo": d.is_demo,
            "source_count": counts.get(d.id, 0),
        })
    return rows


# ------------------------------------------------------------------ reports
@router.get("", dependencies=[Depends(_READ)])
def list_reports() -> dict:
    return {
        "items": [
            {"id": rid, "title": title, "description": desc}
            for rid, title, desc in REPORTS
        ]
    }


@router.get("/review-queue", dependencies=[Depends(_READ)])
def report_review_queue(db: Session = Depends(get_db), limit: int = Query(200, le=1000)) -> dict:
    def rows(model, label_field, *statuses):
        return [
            {"id": r.id, "label": getattr(r, label_field) or r.id,
             "verification_status": r.verification_status,
             "updated_at": r.updated_at.isoformat(), "is_demo": r.is_demo}
            for r in db.scalars(
                select(model).where(model.verification_status.in_(statuses))
                .order_by(model.updated_at.desc()).limit(limit)
            ).all()
        ]

    return {
        "pending_drugs": rows(Drug, "generic_name_en", "imported_pending_review", "pending_verification"),
        "pending_products": rows(Product, "brand_name_en", "imported_pending_review", "pending_verification"),
        "needs_update": rows(Drug, "generic_name_en", "needs_update") + rows(Product, "brand_name_en", "needs_update"),
        "unpublished_imports": [
            {"id": i.id, "filename": i.filename, "status": i.status,
             "total_rows": i.total_rows, "imported_rows": i.imported_rows}
            for i in db.scalars(select(Import).where(Import.status != "completed").limit(limit)).all()
        ],
    }


@router.get("/source-coverage", dependencies=[Depends(_READ)])
def report_source_coverage(db: Session = Depends(get_db)) -> dict:
    rows = _coverage_rows(db)
    with_sources = sum(1 for r in rows if r["source_count"] > 0)
    total = len(rows)
    return {
        "total_drugs": total,
        "with_sources": with_sources,
        "without_sources": total - with_sources,
        "coverage_percent": round(100 * with_sources / total, 1) if total else 0.0,
        "rows": rows,
    }


@router.get("/duplicate-candidates", dependencies=[Depends(_READ)])
def report_duplicate_candidates(db: Session = Depends(get_db), limit: int = Query(200, le=1000)) -> dict:
    rows = db.scalars(
        select(ImportRow).where(ImportRow.duplicate_kind != "").order_by(ImportRow.import_id, ImportRow.row_number).limit(limit)
    ).all()
    return {
        "items": [
            {
                "row_id": r.id, "import_id": r.import_id, "row_number": r.row_number,
                "duplicate_kind": r.duplicate_kind, "duplicate_of_id": r.duplicate_of_id,
                "status": r.status, "created_entity_id": r.created_entity_id,
            }
            for r in rows
        ],
        "policy": "Exact / Possible / Potential — never auto-merged; human review required (§16).",
    }


@router.get("/quality-by-drug", dependencies=[Depends(_READ)])
def report_quality_by_drug(db: Session = Depends(get_db), limit: int = Query(100, le=500)) -> dict:
    dosage_ids = set(db.scalars(select(DrugDosage.drug_id)).all())
    inter_ids = set(db.scalars(select(DrugInteraction.drug_id)).all())
    preg_ids = set(db.scalars(select(DrugPregnancy.drug_id)).all())
    src_ids = set(db.scalars(select(DrugSource.drug_id)).all())

    items = []
    for d in db.scalars(select(Drug).order_by(Drug.updated_at.desc()).limit(limit * 3)).all():
        missing = []
        if not d.generic_name_en or not d.generic_name_ar:
            missing.append("name_incomplete")
        if d.id not in src_ids:
            missing.append("missing_source")
        if d.id not in dosage_ids:
            missing.append("missing_dosage")
        if d.id not in inter_ids:
            missing.append("missing_interactions")
        if d.id not in preg_ids:
            missing.append("missing_pregnancy")
        if d.verification_status != "verified":
            missing.append("unverified_record")
        if missing:
            items.append({
                "id": d.id, "label": _drug_label(d),
                "verification_status": d.verification_status,
                "is_demo": d.is_demo, "missing": missing,
                "missing_count": len(missing),
            })
        if len(items) >= limit:
            break
    items.sort(key=lambda x: -x["missing_count"])
    return {"items": items, "note": "Completeness indicator only — NOT a medical reliability score (§57)."}


@router.get("/task-completion", dependencies=[Depends(_READ)])
def report_task_completion(db: Session = Depends(get_db), limit: int = Query(100, le=500)) -> dict:
    items = []
    for i in db.scalars(select(Import).order_by(Import.created_at.desc()).limit(limit)).all():
        done = i.imported_rows + i.invalid_rows + i.duplicate_rows
        items.append({
            "id": i.id, "filename": i.filename, "file_format": i.file_format,
            "status": i.status, "total_rows": i.total_rows,
            "valid_rows": i.valid_rows, "invalid_rows": i.invalid_rows,
            "duplicate_rows": i.duplicate_rows, "imported_rows": i.imported_rows,
            "completion_percent": round(100 * done / i.total_rows, 1) if i.total_rows else 0.0,
            "created_at": i.created_at.isoformat(),
            "completed_at": i.completed_at.isoformat() if i.completed_at else None,
        })
    return {"items": items}


@router.get("/drugs-needing-update", dependencies=[Depends(_READ)])
def report_drugs_needing_update(db: Session = Depends(get_db), limit: int = Query(200, le=1000)) -> dict:
    items = []
    for model, field in ((Drug, "generic_name_en"), (Product, "brand_name_en")):
        for r in db.scalars(
            select(model).where(model.verification_status == "needs_update")
            .order_by(model.updated_at.desc()).limit(limit)
        ).all():
            items.append({
                "entity_type": "drug" if model is Drug else "product",
                "id": r.id, "label": getattr(r, field) or r.id,
                "updated_at": r.updated_at.isoformat(), "is_demo": r.is_demo,
            })
    return {"items": items}


@router.get("/drugs-without-sources", dependencies=[Depends(_READ)])
def report_drugs_without_sources(db: Session = Depends(get_db)) -> dict:
    rows = [r for r in _coverage_rows(db) if r["source_count"] == 0]
    return {
        "items": rows,
        "note": "Records without any linked source are not publishable (§17).",
    }


@router.get("/unverified-fields", dependencies=[Depends(_READ)])
def report_unverified_fields(db: Session = Depends(get_db)) -> dict:
    unverified_drugs = db.scalar(select(func.count()).select_from(Drug).where(Drug.verification_status != "verified")) or 0
    unverified_products = db.scalar(select(func.count()).select_from(Product).where(Product.verification_status != "verified")) or 0
    dosage_ids = set(db.scalars(select(DrugDosage.drug_id)).all())
    missing_dosage = db.scalar(select(func.count()).select_from(Drug).where(~Drug.id.in_(list(dosage_ids) or [""]))) or 0
    return {
        "unverified_drugs": unverified_drugs,
        "unverified_products": unverified_products,
        "missing_dosage_section": missing_dosage,
        "note": "Unverified content is displayed with visible warnings and is excluded from verified-only views (§18).",
    }


# ------------------------------------------------------------------ CSV export
@router.get("/{report_id}/export.csv")
def export_report_csv(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Generate a downloadable report file (§96) — export is audit-logged (§82)."""
    if not (user.has_permission("data.export") or user.has_permission("settings.manage")):
        raise ForbiddenError("data.export permission required for report export")
    if report_id not in {r[0] for r in REPORTS}:
        from app.core.errors import NotFoundError

        raise NotFoundError(f"Unknown report '{report_id}'")

    from app.services.audit import record_audit

    handler = {
        "review-queue": lambda: report_review_queue(db, 200),
        "source-coverage": lambda: report_source_coverage(db),
        "duplicate-candidates": lambda: report_duplicate_candidates(db, 200),
        "quality-by-drug": lambda: report_quality_by_drug(db, 100),
        "task-completion": lambda: report_task_completion(db, 100),
        "drugs-needing-update": lambda: report_drugs_needing_update(db, 200),
        "drugs-without-sources": lambda: report_drugs_without_sources(db),
        "unverified-fields": lambda: report_unverified_fields(db),
    }[report_id]
    data = handler()

    buf = io.StringIO()
    writer = csv.writer(buf)
    # Flatten: dict rows under first list-like key, scalar summary otherwise.
    list_key = next((k for k, v in data.items() if isinstance(v, list)), None)
    if list_key is not None:
        rows = data[list_key]
        if rows and isinstance(rows[0], dict):
            headers = sorted({k for row in rows for k in row})
            writer.writerow(headers)
            for row in rows:
                writer.writerow([
                    "; ".join(map(str, row[h])) if isinstance(row.get(h), list) else row.get(h, "")
                    for h in headers
                ])
        else:
            writer.writerow([list_key])
            for v in rows:
                writer.writerow([v])
    else:
        writer.writerow(["metric", "value"])
        for k, v in data.items():
            writer.writerow([k, v])

    record_audit(db, action="report.exported", entity_type="report", user_id=user.id, new_value=report_id)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=aph_report_{report_id}.csv"},
    )
