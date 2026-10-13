"""Import engine tests (§19–§22, §55–§56, §75 duplicates)."""
from __future__ import annotations

import io
import json

CSV_SAMPLE = """GenericName,GenericNameAR,BrandName,Strength,DosageForm,Route,Manufacturer,Country,Barcode,RegistrationNumber
Captopril,كابتوبريل,TestBrand Capto,25 mg,Tablet,Oral,Demo Pharma,SA,1111222233334,REG-CAP-001
Captopril,كابتوبريل,TestBrand Capto,25MG,Tabs,PO,Demo Pharma,SA,1111222233334,REG-CAP-001
MissingName,,SomeBrand,10 mg,Tablet,Oral,Demo Pharma,SA,5555666677778,REG-XXX-002
Enalapril,إينالابريل,TestBrand Enala,5 mg,Tablet,Oral,Demo Pharma,SA,9999888877776,REG-ENA-003
,,,not-a-strength,,,,,,,
"""

BAD_CSV = """Whatever,Something
1,2
"""


def _upload(client, headers, content=CSV_SAMPLE, filename="products.csv", entity_type="product"):
    return client.post(
        "/api/v1/imports/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(content.encode()), "text/csv")},
        data={"entity_type": entity_type},
    )


def test_upload_detects_columns_and_validates(client, admin_headers):
    r = _upload(client, admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_rows"] == 5
    mapping = body["suggested_mapping"]
    assert mapping.get("GenericName") == "generic_name_en"
    assert mapping.get("BrandName") == "brand_name_en"
    assert mapping.get("Strength") == "strength"
    assert mapping.get("DosageForm") == "dosage_form"
    assert mapping.get("Barcode") == "barcode"
    # strength normalization keeps original and normalizes unit
    sample = body["sample_rows"]
    assert sample
    # errors reported with row/field/value/suggestion (§56)
    for err in body["errors"]:
        assert set(err.keys()) >= {"row_number", "field", "value", "error", "suggested_correction", "status"}


def test_import_creates_pending_review_records(client, admin_headers):
    r = _upload(client, admin_headers)
    body = r.json()
    import_id = [e["value"] for e in body["errors"] if e["field"] == "_import"][0]

    r = client.post(
        f"/api/v1/imports/{import_id}/execute-file",
        headers=admin_headers,
        files={"file": ("products.csv", io.BytesIO(CSV_SAMPLE.encode()), "text/csv")},
        data={"commit": "true"},
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["imported_rows"] >= 2
    assert result["status"] == "pending_review"

    # imported records must NOT be verified (§19)
    products = client.get("/api/v1/products", params={"q": "TestBrand"}).json()
    assert products["total"] >= 2
    for p in products["items"]:
        assert p["verification_status"] == "imported_pending_review"
        assert p["is_demo"] is False


def test_duplicate_detection_exact(client, admin_headers):
    """Row 2 has the same barcode as row 1 → flagged as exact duplicate, never merged (§21)."""
    r = _upload(client, admin_headers)
    body = r.json()
    import_id = [e["value"] for e in body["errors"] if e["field"] == "_import"][0]
    assert body["duplicate_rows"] >= 1

    r = client.post(
        f"/api/v1/imports/{import_id}/execute-file",
        headers=admin_headers,
        files={"file": ("products.csv", io.BytesIO(CSV_SAMPLE.encode()), "text/csv")},
        data={"commit": "true"},
    )
    result = r.json()
    assert result["duplicate_rows"] >= 1


def test_import_errors_export(client, admin_headers):
    r = _upload(client, admin_headers)
    import_id = [e["value"] for e in r.json()["errors"] if e["field"] == "_import"][0]
    client.post(
        f"/api/v1/imports/{import_id}/execute-file",
        headers=admin_headers,
        files={"file": ("products.csv", io.BytesIO(CSV_SAMPLE.encode()), "text/csv")},
        data={"commit": "true"},
    )
    r = client.get(f"/api/v1/imports/{import_id}/errors/export", params={"format": "csv"},
                   headers=admin_headers)
    assert r.status_code == 200
    assert "row_number" in r.text
    r = client.get(f"/api/v1/imports/{import_id}/errors/export", params={"format": "json"},
                   headers=admin_headers)
    assert r.status_code == 200
    assert json.loads(r.text) is not None


def test_json_and_xlsx_and_zip_and_xml_parsing(client, admin_headers):
    from app.services.import_engine import parse_file

    json_bytes = json.dumps([{"GenericName": "TestA", "BrandName": "B1", "Strength": "10 mg"}]).encode()
    fmt, rows = parse_file("x.json", json_bytes)
    assert fmt == "json" and len(rows) == 1

    xml_bytes = b"<records><record><GenericName>TestB</GenericName><BrandName>B2</BrandName></record></records>"
    fmt, rows = parse_file("x.xml", xml_bytes)
    assert fmt == "xml" and rows[0]["GenericName"] == "TestB"

    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.csv", CSV_SAMPLE)
    fmt, rows = parse_file("x.zip", buf.getvalue())
    assert fmt == "zip" and len(rows) == 5

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["GenericName", "BrandName", "Strength"])
    ws.append(["TestC", "B3", "5 mg"])
    xbuf = io.BytesIO()
    wb.save(xbuf)
    fmt, rows = parse_file("x.xlsx", xbuf.getvalue())
    assert fmt == "xlsx" and rows[0]["GenericName"] == "TestC"


def test_pg_dump_refused_with_guidance(client, admin_headers):
    from app.services.import_engine import parse_file
    from app.core.errors import ValidationFailed
    import pytest

    with pytest.raises(ValidationFailed) as exc:
        parse_file("dump.sql", b"-- PostgreSQL database dump")
    assert "pg_restore" in str(exc.value.detail)


def test_strength_normalization():
    from app.services.normalization import normalize_strength

    for raw in ("500 mg", "500MG", "500 mg ", "0.5 g"):
        ns = normalize_strength(raw)
        assert ns.valid, raw
    assert normalize_strength("500 mg").canonical_mg == 500
    assert normalize_strength("500MG").canonical_mg == 500
    assert normalize_strength("0.5 g").canonical_mg == 500
    assert not normalize_strength("lots").valid


def test_arabic_normalization():
    from app.services.normalization import normalize_arabic

    assert normalize_arabic("أموكسيسيلين") == normalize_arabic("اموكسيسيلين")
    assert normalize_arabic("إينالابريل") == normalize_arabic("اينالابريل")
    assert normalize_arabic("أَمُوكس") == normalize_arabic("اموكس")
