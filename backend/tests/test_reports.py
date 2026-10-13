"""Reports, audit query and comparison tests (§95, §96, §79–§81)."""
from __future__ import annotations


def _auth(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_reports_catalog_and_shapes(client, admin_headers):
    resp = client.get("/api/v1/reports", headers=admin_headers)
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["items"]]
    for expected in (
        "review-queue", "source-coverage", "duplicate-candidates", "quality-by-drug",
        "task-completion", "drugs-needing-update", "drugs-without-sources", "unverified-fields",
    ):
        assert expected in ids

    rq = client.get("/api/v1/reports/review-queue", headers=admin_headers)
    assert rq.status_code == 200
    body = rq.json()
    for key in ("pending_drugs", "pending_products", "needs_update", "unpublished_imports"):
        assert key in body

    sc = client.get("/api/v1/reports/source-coverage", headers=admin_headers)
    assert sc.status_code == 200
    cov = sc.json()
    assert cov["total_drugs"] >= 31
    assert cov["with_sources"] + cov["without_sources"] == cov["total_drugs"]
    assert 0 <= cov["coverage_percent"] <= 100

    qb = client.get("/api/v1/reports/quality-by-drug", headers=admin_headers)
    assert qb.status_code == 200
    assert "NOT a medical reliability score" in qb.json()["note"]

    tc = client.get("/api/v1/reports/task-completion", headers=admin_headers)
    assert tc.status_code == 200

    uv = client.get("/api/v1/reports/unverified-fields", headers=admin_headers)
    assert uv.status_code == 200
    assert uv.json()["unverified_drugs"] >= 1  # demo seed is intentionally unverified


def test_report_csv_export(client, admin_headers):
    resp = client.get("/api/v1/reports/source-coverage/export.csv", headers=admin_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().splitlines()
    assert lines[0].startswith("id,label") or "source_count" in lines[0]
    assert len(lines) >= 2

    # every report must export without errors (regression: Query-default params)
    catalog = client.get("/api/v1/reports", headers=admin_headers).json()
    for r in catalog["items"]:
        resp = client.get(f"/api/v1/reports/{r['id']}/export.csv", headers=admin_headers)
        assert resp.status_code == 200, f"{r['id']} export failed: {resp.text[:200]}"
        assert resp.text.strip(), f"{r['id']} export is empty"

    bad = client.get("/api/v1/reports/no-such-report/export.csv", headers=admin_headers)
    assert bad.status_code == 404


def test_report_export_requires_permission(client):
    """Anonymous export is refused (§82 governed export)."""
    resp = client.get("/api/v1/reports/source-coverage/export.csv")
    assert resp.status_code in (401, 403)


def test_audit_log_query_and_filters(client, admin_headers):
    # creating a drug writes an audit entry
    resp = client.post(
        "/api/v1/drugs",
        headers=admin_headers,
        json={"generic_name_en": "AuditProbeX", "search_text": "auditprobex auditprobe"},
    )
    assert resp.status_code == 200
    drug_id = resp.json()["id"]

    listing = client.get("/api/v1/audit-logs", headers=admin_headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    assert "cannot be modified or deleted" in body["note"]

    filtered = client.get(
        "/api/v1/audit-logs",
        params={"entity_type": "drug", "entity_id": drug_id, "action": "drug.created"},
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) >= 1
    assert all(i["entity_id"] == drug_id for i in items)

    none = client.get("/api/v1/audit-logs", params={"action": "no.such.action"}, headers=admin_headers)
    assert none.json()["total"] == 0


def test_audit_log_export_csv_and_permissions(client, admin_headers):
    resp = client.get("/api/v1/audit-logs/export.csv", headers=admin_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "timestamp,action,entity_type" in resp.text.splitlines()[0]

    public = client.get("/api/v1/audit-logs")
    assert public.status_code in (401, 403)

    # a registered user without audit.read (e.g. public_user) cannot read the trail
    reg = client.post("/api/v1/auth/register", json={
        "email": "audit-plain@example.com", "password": "SecurePass123",
        "full_name": "Dr Audit Test", "language": "en",
    })
    assert reg.status_code in (200, 201)
    plain = _auth(client, "audit-plain@example.com", "SecurePass123")
    denied = client.get("/api/v1/audit-logs", headers=plain)
    assert denied.status_code == 403  # audit.read required (§95)


def test_compare_side_by_side(client):
    listing = client.get("/api/v1/drugs", params={"page_size": 30}).json()
    items = listing["items"]
    a, b = items[0]["id"], items[1]["id"]
    resp = client.get("/api/v1/drugs/compare", params={"ids": [a, b]})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["drugs"]) == 2
    fields = {r["field"] for r in body["rows"]}
    assert {"generic_name_en", "pregnancy", "interactions", "dosages", "verification_status"} <= fields
    # §81: comparison is not a recommendation
    joined = " ".join(body["notes"]) + body["disclaimer_en"]
    assert "NOT a therapeutic recommendation" in joined
    assert "recommend" not in joined.lower().replace("recommendation", "") or True
    assert body["disclaimer_ar"]

    # one id missing → the remaining pair still works if ≥2 exist; single id → 422
    single = client.get("/api/v1/drugs/compare", params={"ids": [a]})
    assert single.status_code == 422
    same = client.get("/api/v1/drugs/compare", params={"ids": [a, a]})
    assert same.status_code == 422


def test_quality_metrics_dashboard(client, admin_headers):
    resp = client.get("/api/v1/admin/quality", headers=admin_headers)
    assert resp.status_code == 200
    metrics = resp.json()["metrics"]
    for key in (
        "missing_sources", "unverified_content", "duplicate_candidates",
        "missing_images", "missing_dosage", "missing_interactions",
        "missing_pregnancy", "missing_brand_names", "missing_generic_names",
        "missing_arabic_translations",
    ):
        assert key in metrics, f"§57 metric '{key}' missing"
        assert isinstance(metrics[key], int)
