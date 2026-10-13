"""APH bulk import engine (§19–§22, §55–§56, §97–§98).

Pipeline:
  UPLOAD -> VALIDATION -> COLUMN MAPPING -> NORMALIZATION -> VALIDATION
  -> DUPLICATE DETECTION -> CATEGORY MAPPING -> SOURCE ATTACHMENT
  -> IMPORT -> PENDING REVIEW -> PHARMACIST REVIEW -> VERIFICATION -> PUBLISH

Imported rows are NEVER blindly published: created records land in
`imported_pending_review` status and must pass the verification workflow.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree

from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models import (
    Drug,
    DrugSynonym,
    Import,
    ImportErrorRecord,
    ImportRow,
    Manufacturer,
    Product,
    ProductIngredient,
    Source,
    VerificationStatus,
)
from app.services.duplicates import find_product_duplicates
from app.services.normalization import (
    normalize_country,
    normalize_dosage_form,
    normalize_route,
    normalize_strength,
    normalize_text,
    parse_strength_field,
)
from app.services.search import build_drug_search_fields, build_product_search_fields

NOT_AVAILABLE = "Not available / Requires verified source"

# Canonical field name -> accepted source column aliases (lowercased)
FIELD_ALIASES: Dict[str, List[str]] = {
    "generic_name_en": ["genericnameen", "genericname", "generic_name", "generic_name_en", "generic", "scientificname", " المادة"],
    "generic_name_ar": ["genericnamear", "generic_name_ar", "genericnamearabic", "الاسم العلمي"],
    "brand_name_en": ["brandnameen", "brandname", "brand_name", "brand_name_en", "tradename", "productname"],
    "brand_name_ar": ["brandnamear", "brand_name_ar", "brandnamearabic", "الاسم التجاري"],
    "active_ingredient": ["activeingredient", "active_ingredient", "ingredient", "المواد الفعالة"],
    "strength": ["strength", "القوة", "concentration"],
    "strength_value": ["strengthvalue", "strength_value"],
    "strength_unit": ["strengthunit", "strength_unit"],
    "dosage_form": ["dosageform", "dosage_form", "form", "الشكل الصيدلاني"],
    "route": ["route", "طريقة الاستعمال"],
    "manufacturer": ["manufacturer", "company", "المصنع", "الشركة"],
    "country": ["country", "manufacturercountry", "manufacturercountry", "البلد"],
    "marketing_country": ["marketingcountry", "marketing_country"],
    "body_system": ["bodysystem", "body_system", "system", "الجهاز"],
    "therapeutic_group": ["therapeuticgroup", "therapeutic_group"],
    "pharmacological_class": ["pharmacologicalclass", "pharmacological_class", "drugclass"],
    "mechanism": ["mechanism", "mechanismofaction", "mechanism_of_action", "آلية العمل"],
    "indications": ["indications", "indication", "uses", "الاستطبابات"],
    "contraindications": ["contraindications", "الموانع"],
    "warnings": ["warnings", "التحذيرات"],
    "precautions": ["precautions", "الاحتياطات"],
    "side_effects": ["sideeffects", "side_effects", "adverseeffects", "الاثار الجانبية"],
    "interactions": ["interactions", "druginteractions", "التداخلات"],
    "food_interactions": ["foodinteractions", "food_interactions"],
    "dosage": ["dosage", "dose", "الجرعة"],
    "pediatric_dosage": ["pediatricdosage", "pediatric_dosage", "childdose"],
    "geriatric_dosage": ["geriatricdosage", "geriatric_dosage"],
    "renal_adjustment": ["renaladjustment", "renal_adjustment"],
    "hepatic_adjustment": ["hepaticadjustment", "hepatic_adjustment"],
    "pregnancy": ["pregnancy", "الحمل"],
    "lactation": ["lactation", "breastfeeding", "الرضاعة"],
    "barcode": ["barcode", "gtin", "ean", "الباركود"],
    "registration_number": ["registrationnumber", "registration_number", "regnumber", "رقم التسجيل"],
    "image_url": ["imageurl", "image_url", "image", "الصورة"],
    "source_url": ["sourceurl", "source_url", "reference", "referenceurl"],
    "verification_status": ["verificationstatus", "verification_status", "status"],
}


@dataclass
class MappedRow:
    row_number: int
    raw: Dict[str, Any]
    data: Dict[str, str]
    errors: List[Tuple[str, str, str]] = field(default_factory=list)  # field, value, error
    duplicate_kind: str = ""
    duplicate_of: str = ""
    valid: bool = True


@dataclass
class ImportPreview:
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    columns_detected: List[str]
    suggested_mapping: Dict[str, str]
    sample_rows: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]


# ------------------------------------------------------------------ parsers
def parse_file(filename: str, content: bytes, file_format: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse an uploaded file into a list of raw dict rows.

    Returns (detected_format, rows). Raises ValidationFailed on unreadable input.
    """
    fmt = (file_format or _detect_format(filename, content)).lower()
    if fmt in ("csv", "txt"):
        return fmt, _parse_csv(content)
    if fmt == "json":
        return fmt, _parse_json(content)
    if fmt in ("xlsx", "xls", "excel"):
        return fmt, _parse_xlsx(content)
    if fmt == "xml":
        return fmt, _parse_xml(content)
    if fmt == "zip":
        return fmt, _parse_zip(content)
    if fmt in ("sqlite", "sqlite3", "db"):
        return fmt, _parse_sqlite(content)
    if fmt in ("pg_dump", "sql", "postgresql"):
        # PostgreSQL dumps must be loaded by a DBA with pg_restore — refuse to fake it.
        raise ValidationFailed(
            "PostgreSQL dump files cannot be parsed in-process. Load the dump with pg_restore "
            "into a staging database and use the API import source instead.",
            {"format": fmt},
        )
    raise ValidationFailed(f"Unsupported import format: {fmt}", {"filename": filename})


def _detect_format(filename: str, content: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".json"):
        return "json"
    if name.endswith((".xlsx", ".xls")):
        return "xlsx"
    if name.endswith(".xml"):
        return "xml"
    if name.endswith(".zip"):
        return "zip"
    if name.endswith((".sqlite", ".sqlite3", ".db")):
        return "sqlite"
    if name.endswith(".sql"):
        return "pg_dump"
    if content[:2] == b"PK":
        return "zip"
    if content[:1] in (b"{", b"["):
        return "json"
    return "csv"


def _parse_csv(content: bytes) -> List[Dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValidationFailed("CSV file has no header row.")
    out: List[Dict[str, Any]] = []
    for row in reader:
        item: Dict[str, Any] = {}
        for key, value in row.items():
            if key is None:
                # extra values beyond the header — keep them, never crash
                if isinstance(value, list):
                    item["_extra"] = " ".join(str(v) for v in value)
                elif value is not None:
                    item["_extra"] = str(value)
                continue
            if isinstance(value, list):
                item[key.strip()] = " ".join(str(v) for v in value).strip()
            else:
                item[key.strip()] = "" if value is None else str(value).strip()
        out.append(item)
    return out


def _parse_json(content: bytes) -> List[Dict[str, Any]]:
    try:
        data = json.loads(content.decode("utf-8-sig", errors="replace"))
    except json.JSONDecodeError as exc:
        raise ValidationFailed(f"Invalid JSON: {exc}") from exc
    if isinstance(data, dict):
        for key in ("items", "rows", "data", "records", "products", "drugs"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValidationFailed("JSON import must contain an array of records.")
    return [dict(row) for row in data if isinstance(row, dict)]


def _parse_xlsx(content: bytes) -> List[Dict[str, Any]]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ValidationFailed(f"Unreadable Excel file: {exc}") from exc
    ws = wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    try:
        headers = next(rows_iter)
    except StopIteration:
        raise ValidationFailed("Excel sheet is empty.") from None
    headers = [str(h).strip() if h is not None else "" for h in headers]
    out = []
    for row in rows_iter:
        if row is None or all(c is None for c in row):
            continue
        out.append({headers[i]: ("" if i >= len(row) or row[i] is None else str(row[i]).strip()) for i in range(len(headers))})
    return out


def _parse_xml(content: bytes) -> List[Dict[str, Any]]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise ValidationFailed(f"Invalid XML: {exc}") from exc
    out = []
    for elem in list(root):
        record = {child.tag: (child.text or "").strip() for child in list(elem)}
        if record:
            out.append(record)
    return out


def _parse_zip(content: bytes) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for name in zf.namelist():
            lower = name.lower()
            if lower.endswith(".csv"):
                rows.extend(_parse_csv(zf.read(name)))
            elif lower.endswith(".json"):
                rows.extend(_parse_json(zf.read(name)))
            elif lower.endswith((".xlsx", ".xls")):
                rows.extend(_parse_xlsx(zf.read(name)))
    if not rows:
        raise ValidationFailed("ZIP archive contains no supported data files (csv/json/xlsx).")
    return rows


def _parse_sqlite(content: bytes) -> List[Dict[str, Any]]:
    import tempfile, os

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp.write(content)
        path = tmp.name
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        if not tables:
            raise ValidationFailed("SQLite database contains no tables.")
        # pick the table with the most rows
        best, best_count = None, -1
        for t in tables:
            count = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            if count > best_count:
                best, best_count = t, count
        rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{best}"')]
        conn.close()
        return [{str(k): ("" if v is None else str(v).strip()) for k, v in row.items()} for row in rows]
    finally:
        os.unlink(path)


# ------------------------------------------------------------------ mapping
def suggest_column_mapping(columns: List[str]) -> Dict[str, str]:
    """Map source columns -> canonical fields using alias tables."""
    mapping: Dict[str, str] = {}
    used = set()
    lowered = {c: re.sub(r"[\s_\-]+", "", (c or "").lower()) for c in columns}
    for canonical, aliases in FIELD_ALIASES.items():
        norm_aliases = {re.sub(r"[\s_\-]+", "", a.lower()) for a in aliases}
        for col, low in lowered.items():
            if col in used:
                continue
            if low in norm_aliases:
                mapping[col] = canonical
                used.add(col)
                break
    return mapping


# ------------------------------------------------------------------ normalize/validate
def normalize_row(raw: Dict[str, Any], mapping: Dict[str, str]) -> MappedRow:
    data: Dict[str, str] = {}
    errors: List[Tuple[str, str, str]] = []

    for src_col, canonical in mapping.items():
        value = raw.get(src_col, "")
        data[canonical] = "" if value is None else str(value).strip()

    # strength normalization: keep original in data['strength'], add normalized parts
    if data.get("strength"):
        strength_display, value, unit = parse_strength_field(data["strength"])
        data["strength"] = strength_display
        data.setdefault("strength_value", value)
        data.setdefault("strength_unit", unit)
        ns = normalize_strength(data["strength"])
        if data["strength"] and not ns.valid:
            errors.append(("strength", data["strength"], "Unrecognized strength format — expected e.g. '500 mg'"))

    if data.get("dosage_form"):
        data["dosage_form_normalized"] = normalize_dosage_form(data["dosage_form"])
    if data.get("route"):
        data["route_normalized"] = normalize_route(data["route"])
    if data.get("country"):
        data["country_normalized"] = normalize_country(data["country"])

    # required-field validation
    if not data.get("generic_name_en") and not data.get("generic_name_ar"):
        errors.append(("generic_name_en", "", "Missing generic name (English or Arabic required)"))
    if data.get("strength") and not data.get("dosage_form"):
        errors.append(("dosage_form", "", "Missing dosage form"))

    return MappedRow(row_number=0, raw=raw, data=data, errors=errors, valid=not errors)


# ------------------------------------------------------------------ pipeline
def prepare_preview(
    db: Session,
    rows: List[Dict[str, Any]],
    mapping: Dict[str, str],
    entity_type: str = "product",
) -> ImportPreview:
    columns = sorted({k for row in rows[:50] for k in row.keys()})
    if not mapping:
        mapping = suggest_column_mapping(columns)

    valid = invalid = duplicates = 0
    errors: List[Dict[str, Any]] = []
    sample: List[Dict[str, Any]] = []
    seen_barcodes: Dict[str, int] = {}
    seen_regs: Dict[str, int] = {}
    seen_names: Dict[str, int] = {}

    for idx, raw in enumerate(rows[:500], start=1):
        mapped = normalize_row(raw, mapping)
        mapped.row_number = idx
        if mapped.errors:
            invalid += 1
            for fld, val, err in mapped.errors:
                errors.append({
                    "row_number": idx, "field": fld, "value": val, "error": err,
                    "suggested_correction": _suggest(fld, val), "status": "open",
                })
        else:
            valid += 1
        if entity_type == "product":
            # in-file duplicates first (rows earlier in the same batch)
            barcode = mapped.data.get("barcode", "")
            reg = mapped.data.get("registration_number", "")
            name_key_str = "|".join([
                normalize_text(mapped.data.get("brand_name_en", "")),
                normalize_text(mapped.data.get("strength", "")),
                normalize_text(mapped.data.get("dosage_form", "")),
            ])
            if barcode and barcode in seen_barcodes:
                mapped.duplicate_kind = "exact"
                duplicates += 1
            elif reg and reg in seen_regs:
                mapped.duplicate_kind = "exact"
                duplicates += 1
            elif name_key_str.count("|") == 2 and name_key_str.strip("|") and name_key_str in seen_names:
                mapped.duplicate_kind = "possible"
                duplicates += 1
            else:
                dupes = find_product_duplicates(
                    db,
                    brand_name_en=mapped.data.get("brand_name_en", ""),
                    brand_name_ar=mapped.data.get("brand_name_ar", ""),
                    strength=mapped.data.get("strength", ""),
                    dosage_form=mapped.data.get("dosage_form_normalized", mapped.data.get("dosage_form", "")),
                    manufacturer_name=mapped.data.get("manufacturer", ""),
                    barcode=mapped.data.get("barcode", ""),
                    registration_number=mapped.data.get("registration_number", ""),
                )
                if dupes:
                    duplicates += 1
                    mapped.duplicate_kind = dupes[0].kind
            if barcode:
                seen_barcodes[barcode] = idx
            if reg:
                seen_regs[reg] = idx
            if name_key_str.strip("|"):
                seen_names[name_key_str] = idx
        if len(sample) < 10:
            sample.append({"row_number": idx, "data": mapped.data, "valid": mapped.valid,
                           "duplicate_kind": mapped.duplicate_kind})

    return ImportPreview(
        total_rows=len(rows),
        valid_rows=valid if len(rows) <= 500 else valid,  # preview validates first 500
        invalid_rows=invalid,
        duplicate_rows=duplicates,
        columns_detected=columns,
        suggested_mapping=mapping,
        sample_rows=sample,
        errors=errors[:100],
    )


def _suggest(field: str, value: str) -> str:
    if field == "strength":
        return "Use a numeric value followed by a unit, e.g. '500 mg'"
    if field == "dosage_form":
        return "Use a standard dosage form (Tablet, Capsule, Injection, ...)"
    if field == "generic_name_en":
        return "Provide the generic (scientific) name, not the brand name"
    return ""


def execute_import(
    db: Session,
    import_record: Import,
    rows: List[Dict[str, Any]],
    mapping: Dict[str, str],
    user_id: Optional[str] = None,
    source_id: Optional[str] = None,
) -> Import:
    """Create records from import rows. Everything lands as
    `imported_pending_review` — never as verified (§19)."""
    import json as _json

    entity_type = import_record.entity_type
    total = len(rows)
    valid = invalid = dup = imported = 0

    for idx, raw in enumerate(rows, start=1):
        mapped = normalize_row(raw, mapping)
        mapped.row_number = idx

        row = ImportRow(
            import_id=import_record.id,
            row_number=idx,
            raw_data=_json.dumps(raw, ensure_ascii=False, default=str),
            normalized_data=_json.dumps(mapped.data, ensure_ascii=False, default=str),
        )

        if mapped.errors:
            invalid += 1
            row.status = "invalid"
            for fld, val, err in mapped.errors:
                db.add(ImportErrorRecord(
                    import_id=import_record.id, row_number=idx, field=fld,
                    value=val, error=err, suggested_correction=_suggest(fld, val),
                ))
            db.add(row)
            continue

        try:
            if entity_type == "drug":
                created_id = _create_drug_from_row(db, mapped.data, user_id=user_id, source_id=source_id)
            else:
                created_id, dup_kind, dup_of = _create_product_from_row(db, mapped.data, user_id=user_id, source_id=source_id)
                if dup_kind:
                    dup += 1
                    row.duplicate_kind = dup_kind
                    row.duplicate_of_id = dup_of
                    if dup_kind == "exact":
                        row.status = "duplicate_exact"
                        db.add(row)
                        continue
            row.created_entity_id = created_id
            row.status = "imported"
            imported += 1
        except Exception as exc:  # row-level failure must not kill the batch
            invalid += 1
            row.status = "failed"
            db.add(ImportErrorRecord(
                import_id=import_record.id, row_number=idx, field="record",
                value="", error=str(exc)[:500], suggested_correction="Fix the row and use 'retry failed rows'",
            ))
        valid += 1 if row.status == "imported" else 0
        db.add(row)

    import_record.total_rows = total
    import_record.valid_rows = imported
    import_record.invalid_rows = invalid
    import_record.duplicate_rows = dup
    import_record.imported_rows = imported
    import_record.status = "pending_review"
    db.flush()
    return import_record


def _create_drug_from_row(db: Session, data: Dict[str, str], user_id: Optional[str], source_id: Optional[str]) -> str:
    from app.models import VerificationStatus as VS

    drug = Drug(
        generic_name_en=data.get("generic_name_en", ""),
        generic_name_ar=data.get("generic_name_ar", ""),
        mechanism_en=data.get("mechanism", ""),
        mechanism_ar="",
        overview_en="",
        is_demo=False,
        verification_status=VS.IMPORTED_PENDING_REVIEW.value,
    )
    drug.created_by = user_id
    drug.updated_by = user_id
    db.add(drug)
    db.flush()
    syn = DrugSynonym(drug_id=drug.id, term=data.get("generic_name_en", ""), language="en")
    db.add(syn)
    build_drug_search_fields(db, drug)
    return drug.id


def _create_product_from_row(
    db: Session, data: Dict[str, str], user_id: Optional[str], source_id: Optional[str]
) -> Tuple[str, str, str]:
    dupes = find_product_duplicates(
        db,
        brand_name_en=data.get("brand_name_en", ""),
        brand_name_ar=data.get("brand_name_ar", ""),
        strength=data.get("strength", ""),
        dosage_form=data.get("dosage_form_normalized", ""),
        manufacturer_name=data.get("manufacturer", ""),
        barcode=data.get("barcode", ""),
        registration_number=data.get("registration_number", ""),
    )
    if dupes and dupes[0].kind == "exact":
        return "", "exact", dupes[0].product_id

    manufacturer = None
    if data.get("manufacturer"):
        from app.services.normalization import normalize_manufacturer
        manu_key = normalize_manufacturer(data["manufacturer"])
        for m in db.query(Manufacturer).filter(Manufacturer.name_en.ilike(f"%{data['manufacturer'][:20]}%")).limit(5).all():
            if normalize_manufacturer(m.name_en) == manu_key:
                manufacturer = m
                break
        if manufacturer is None:
            manufacturer = Manufacturer(name_en=data["manufacturer"][:255], name_ar="")
            db.add(manufacturer)
            db.flush()

    product = Product(
        brand_name_en=data.get("brand_name_en", "")[:255],
        brand_name_ar=data.get("brand_name_ar", "")[:255],
        strength=data.get("strength", ""),
        strength_value=data.get("strength_value", ""),
        strength_unit=data.get("strength_unit", ""),
        dosage_form=data.get("dosage_form_normalized", ""),
        route=data.get("route_normalized", ""),
        barcode=data.get("barcode", ""),
        registration_number=data.get("registration_number", ""),
        manufacturer_id=manufacturer.id if manufacturer else None,
        is_demo=False,
        verification_status=VerificationStatus.IMPORTED_PENDING_REVIEW.value,
    )
    product.created_by = user_id
    product.updated_by = user_id
    db.add(product)
    db.flush()

    ing_name = data.get("active_ingredient") or data.get("generic_name_en") or ""
    if ing_name:
        db.add(ProductIngredient(
            product_id=product.id,
            ingredient_name_en=ing_name[:255],
            ingredient_name_ar=data.get("generic_name_ar", "")[:255],
            strength=data.get("strength", ""),
            is_primary=True,
        ))
    build_product_search_fields(product)
    dup_kind = dupes[0].kind if dupes else ""
    return product.id, dup_kind, dupes[0].product_id if dupes else ""


def retry_failed_rows(db: Session, import_record: Import, user_id: Optional[str] = None) -> Dict[str, int]:
    """Re-process rows that previously failed (§98)."""
    from app.models import ImportRowStatus

    retried = succeeded = 0
    mapping = json.loads(import_record.column_mapping or "{}")
    for row in db.query(ImportRow).filter(
        ImportRow.import_id == import_record.id,
        ImportRow.status.in_(["failed", "invalid"]),
    ).all():
        retried += 1
        raw = json.loads(row.raw_data or "{}")
        mapped = normalize_row(raw, mapping)
        if mapped.errors:
            continue
        try:
            if import_record.entity_type == "drug":
                created = _create_drug_from_row(db, mapped.data, user_id=user_id, source_id=None)
            else:
                created, dup_kind, dup_of = _create_product_from_row(db, mapped.data, user_id=user_id, source_id=None)
                row.duplicate_kind = dup_kind
                row.duplicate_of_id = dup_of
            row.created_entity_id = created
            row.status = ImportRowStatus.IMPORTED.value
            succeeded += 1
        except Exception as exc:
            row.status = ImportRowStatus.FAILED.value
            db.add(ImportErrorRecord(
                import_id=import_record.id, row_number=row.row_number, field="record",
                value="", error=str(exc)[:500], suggested_correction="",
            ))
    db.flush()
    return {"retried": retried, "succeeded": succeeded}
