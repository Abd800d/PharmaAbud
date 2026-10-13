"""Security tests (§46–§47, §77): uploads, audit integrity, error handling."""
from __future__ import annotations

import io

# minimal valid 1x1 PNG
PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
    b"\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _create_product(client, headers):
    r = client.post("/api/v1/products", json={
        "brand_name_en": "SecTest Brand", "strength": "10 mg", "dosage_form": "tablet",
    }, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_image_upload_rejects_executables(client, admin_headers):
    product_id = _create_product(client, admin_headers)
    r = client.post(
        f"/api/v1/products/{product_id}/images",
        headers=admin_headers,
        files={"file": ("evil.exe", io.BytesIO(b"MZ\x90\x00" + b"\x00" * 100), "application/octet-stream")},
        data={"kind": "front_package"},
    )
    assert r.status_code == 422
    assert "Allowed: JPEG, PNG, WebP" in r.text or "Unsupported image type" in r.text


def test_image_upload_rejects_spoofed_mime(client, admin_headers):
    product_id = _create_product(client, admin_headers)
    r = client.post(
        f"/api/v1/products/{product_id}/images",
        headers=admin_headers,
        files={"file": ("fake.png", io.BytesIO(b"<html><script>alert(1)</script></html>"), "image/png")},
        data={"kind": "front_package"},
    )
    assert r.status_code == 422


def test_image_upload_accepts_png(client, admin_headers):
    product_id = _create_product(client, admin_headers)
    r = client.post(
        f"/api/v1/products/{product_id}/images",
        headers=admin_headers,
        files={"file": ("pack.png", io.BytesIO(PNG_1PX), "image/png")},
        data={"kind": "front_package", "source": "test", "copyright_info": "test"},
    )
    assert r.status_code == 200, r.text


def test_image_review_queue_requires_permission(client, public_headers, admin_headers):
    r = client.get("/api/v1/images/review-queue", headers=public_headers)
    assert r.status_code == 403
    r = client.get("/api/v1/images/review-queue", headers=admin_headers)
    assert r.status_code == 200


def test_audit_logs_are_append_only_for_users(client, admin_headers, public_headers):
    r = client.get("/api/v1/audit-logs", headers=public_headers)
    assert r.status_code == 403
    r = client.get("/api/v1/audit-logs", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "append-only" in body["note"]
    assert body["items"], "expected audit entries from seeding/login"
    actions = {item["action"] for item in body["items"]}
    assert "user.login" in actions


def test_audit_captures_drug_creation(client, admin_headers):
    client.post("/api/v1/drugs", json={"generic_name_en": "Auditmol"}, headers=admin_headers)
    r = client.get("/api/v1/audit-logs", params={"action": "drug.created"}, headers=admin_headers)
    assert r.json()["items"]


def test_errors_never_leak_stack_traces(client):
    r = client.get("/api/v1/drugs/does-not-exist")
    assert r.status_code == 404
    assert "Traceback" not in r.text
    assert r.json()["error"]["code"] == "not_found"

    r = client.get("/api/v1/drugs")
    assert r.status_code == 200


def test_sql_injection_input_is_parameterized(client):
    r = client.get("/api/v1/search", params={"q": "'; DROP TABLE drugs; --"})
    assert r.status_code == 200
    # drugs table still works
    assert client.get("/api/v1/drugs").status_code == 200


def test_openapi_documentation_available(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"].startswith("AbdulmajeedPharma")
    assert "/api/v1/drugs" in spec["paths"]
    assert "/api/v1/search" in spec["paths"]
    assert "/api/v1/ai/ask" in spec["paths"]


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_export_is_audited(client, admin_headers):
    r = client.get("/api/v1/admin/export", params={"entity": "products", "format": "csv"}, headers=admin_headers)
    assert r.status_code == 200
    r = client.get("/api/v1/audit-logs", params={"action": "data.exported"}, headers=admin_headers)
    assert r.json()["items"]


def test_quality_dashboard(client, admin_headers):
    r = client.get("/api/v1/admin/quality", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "NOT a medical reliability score" in body["score_note"]
    assert 0 <= body["score"] <= 100


def test_dashboard_stats(client, admin_headers):
    r = client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert r.status_code == 200
    totals = r.json()["totals"]
    assert totals["drugs"] >= 25
    assert totals["products"] >= 25
    assert len(r.json()["charts"]["products_by_system"]) == 18
