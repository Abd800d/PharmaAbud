"""Import engine endpoints (§19, §55–§56, §97–§98)."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.errors import NotFoundError, ValidationFailed
from app.db.session import get_db
from app.models import Import, ImportErrorRecord, ImportRow, User
from app.schemas.import_ import ImportExecuteRequest, ImportErrorOut, ImportOut, ImportPreviewOut
from app.services import import_engine
from app.services.audit import record_audit

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("", response_model=dict, dependencies=[Depends(require_permission("import.create"))])
def list_imports(db: Session = Depends(get_db), page: int = 1, limit: int = 25) -> dict:
    from sqlalchemy import func

    total = db.scalar(select(func.count()).select_from(Import)) or 0
    rows = db.scalars(select(Import).order_by(Import.created_at.desc()).offset((page - 1) * limit).limit(limit)).all()
    return {
        "items": [ImportOut.model_validate(r).model_dump() for r in rows],
        "total": total, "page": page, "limit": limit, "has_more": page * limit < total,
    }


@router.post("/upload", response_model=ImportPreviewOut,
             dependencies=[Depends(require_permission("import.create"))])
async def upload_and_preview(
    request: Request,
    file: UploadFile = File(...),
    entity_type: str = Form("product"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportPreviewOut:
    """Step 1–5: upload → format detection → column mapping → validation preview."""
    content = await file.read()
    if len(content) > 64 * 1024 * 1024:
        raise ValidationFailed("Import file exceeds 64 MB. Use the background job pipeline for larger datasets.")
    try:
        fmt, rows = import_engine.parse_file(file.filename or "upload.csv", content)
    except ValidationFailed:
        raise
    except Exception:
        raise ValidationFailed("File could not be parsed.")

    if not rows:
        raise ValidationFailed("No data rows found in the file.")

    mapping = import_engine.suggest_column_mapping(sorted({key for row in rows[:50] for key in row.keys()}))
    preview = import_engine.prepare_preview(db, rows, mapping, entity_type=entity_type)

    record = Import(
        filename=(file.filename or "upload")[:255],
        file_format=fmt,
        entity_type=entity_type,
        status="uploaded",
        column_mapping=json.dumps(mapping, ensure_ascii=False),
        total_rows=len(rows),
        created_by=user.id,
    )
    db.add(record)
    record_audit(db, action="import.uploaded", entity_type="import", entity_id=record.id,
                 user_id=user.id, new_value=record.filename,
                 ip_address=request.client.host if request.client else "")
    db.flush()

    preview_dict = preview.__dict__
    preview_dict["import_id"] = record.id  # surfaced via response extras below
    return ImportPreviewOut(
        total_rows=preview.total_rows,
        valid_rows=preview.valid_rows,
        invalid_rows=preview.invalid_rows,
        duplicate_rows=preview.duplicate_rows,
        columns_detected=preview.columns_detected,
        suggested_mapping=preview.suggested_mapping,
        sample_rows=preview.sample_rows,
        errors=preview.errors + [{"row_number": 0, "field": "_import", "value": record.id,
                                  "error": "", "suggested_correction": "", "status": "info"}],
    )


@router.post("/{import_id}/execute", response_model=ImportOut,
             dependencies=[Depends(require_permission("import.approve"))])
def execute_import(
    import_id: str,
    payload: ImportExecuteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportOut:
    """Steps 6–8: duplicates report → import → pending review queue.

    Records are created as `imported_pending_review` — never auto-published.
    """
    record = db.get(Import, import_id)
    if record is None:
        raise NotFoundError("Import", import_id)
    if not payload.commit:
        raise ValidationFailed("Set commit=true to execute the import. Imported rows go to pending review, not published.")

    # re-parse the original file content is not retained; rows were staged at upload in production.
    # For this engine, execute requires the rows to be present in the request pipeline:
    # the stored column mapping is applied to re-uploaded content via /execute-file.
    raise ValidationFailed("Use POST /imports/{id}/execute-file with the same file to commit the import.")


@router.post("/{import_id}/execute-file", response_model=ImportOut,
             dependencies=[Depends(require_permission("import.approve"))])
async def execute_import_with_file(
    import_id: str,
    file: UploadFile = File(...),
    commit: bool = Form(True),
    source_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportOut:
    record = db.get(Import, import_id)
    if record is None:
        raise NotFoundError("Import", import_id)
    if not commit:
        raise ValidationFailed("Set commit=true to execute the import.")

    content = await file.read()
    _fmt, rows = import_engine.parse_file(file.filename or record.filename, content)
    mapping = json.loads(record.column_mapping or "{}")
    import_engine.execute_import(db, record, rows, mapping, user_id=user.id, source_id=source_id)

    record_audit(db, action="import.completed", entity_type="import", entity_id=record.id,
                 user_id=user.id, new_value=f"imported={record.imported_rows}")
    db.flush()
    return ImportOut.model_validate(record)


@router.get("/{import_id}", response_model=ImportOut,
            dependencies=[Depends(require_permission("import.create"))])
def get_import(import_id: str, db: Session = Depends(get_db)) -> ImportOut:
    record = db.get(Import, import_id)
    if record is None:
        raise NotFoundError("Import", import_id)
    return ImportOut.model_validate(record)


@router.get("/{import_id}/errors", response_model=dict,
            dependencies=[Depends(require_permission("import.create"))])
def import_errors(import_id: str, db: Session = Depends(get_db), limit: int = 200) -> dict:
    rows = db.scalars(
        select(ImportErrorRecord).where(ImportErrorRecord.import_id == import_id)
        .order_by(ImportErrorRecord.row_number).limit(limit)
    ).all()
    return {
        "items": [ImportErrorOut.model_validate(r).model_dump() for r in rows],
        "export_formats": ["csv", "json"],
    }


@router.get("/{import_id}/errors/export", dependencies=[Depends(require_permission("import.create"))])
def export_errors(import_id: str, format: str = "csv", db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ImportErrorRecord).where(ImportErrorRecord.import_id == import_id)
        .order_by(ImportErrorRecord.row_number)
    ).all()
    if format == "json":
        import json as _json

        return PlainTextResponse(
            _json.dumps([{
                "row_number": r.row_number, "field": r.field, "value": r.value,
                "error": r.error, "suggested_correction": r.suggested_correction, "status": r.status,
            } for r in rows], ensure_ascii=False, indent=2),
            media_type="application/json",
        )
    lines = ["row_number,field,value,error,suggested_correction,status"]
    for r in rows:
        safe = lambda s: '"' + str(s).replace('"', '""') + '"'
        lines.append(",".join(safe(x) for x in [r.row_number, r.field, r.value, r.error, r.suggested_correction, r.status]))
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


@router.post("/{import_id}/retry-failed", response_model=dict,
             dependencies=[Depends(require_permission("import.approve"))])
def retry_failed(import_id: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> dict:
    record = db.get(Import, import_id)
    if record is None:
        raise NotFoundError("Import", import_id)
    result = import_engine.retry_failed_rows(db, record, user_id=user.id)
    record_audit(db, action="import.retried", entity_type="import", entity_id=record.id,
                 user_id=user.id, new_value=result)
    db.flush()
    return result
