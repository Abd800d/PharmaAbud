"""Monograph editing, source links, translations, favorites, requests (§6, §11, §25, §58, §69)."""
from __future__ import annotations

NOT_AVAILABLE = "Not available / Requires verified source"


def _drug_id(client, name="Enalapril"):
    data = client.get("/api/v1/search", params={"q": name, "kinds": "drug"}).json()
    return next(h["id"] for h in data["items"] if h["kind"] == "drug" and h["name_en"] == name)


def test_set_full_monograph_sections(client, admin_headers):
    drug_id = _drug_id(client, "Amlodipine")

    r = client.put(f"/api/v1/drugs/{drug_id}/indications", json={
        "items": [
            {"text_en": "Hypertension (demo edit)", "text_ar": "ارتفاع الضغط", "is_off_label": False},
            {"text_en": "Raynaud (demo, off-label)", "is_off_label": True},
        ],
    }, headers=admin_headers)
    assert r.status_code == 200, r.text

    r = client.put(f"/api/v1/drugs/{drug_id}/contraindications", json={
        "items": [{"text_en": "Severe hypotension (demo)", "severity": "absolute"}],
    }, headers=admin_headers)
    assert r.status_code == 200

    r = client.put(f"/api/v1/drugs/{drug_id}/warnings", json={
        "items": [{"text_en": "Demo warning", "severity": "boxed"}],
    }, headers=admin_headers)
    assert r.status_code == 200

    r = client.put(f"/api/v1/drugs/{drug_id}/side-effects", json={
        "items": [{"text_en": "Peripheral edema (demo)", "frequency": "common", "is_serious": False}],
    }, headers=admin_headers)
    assert r.status_code == 200

    r = client.put(f"/api/v1/drugs/{drug_id}/interactions", json={
        "items": [{"text_en": "Demo interaction", "interacting_agent": "Simvastatin", "severity": "major"}],
    }, headers=admin_headers)
    assert r.status_code == 200

    r = client.put(f"/api/v1/drugs/{drug_id}/dosages", json={
        "items": [
            {"population": "adult", "text_en": NOT_AVAILABLE, "is_verified": False},
            {"population": "pediatric", "text_en": NOT_AVAILABLE, "is_verified": False},
        ],
    }, headers=admin_headers)
    assert r.status_code == 200

    detail = client.get(f"/api/v1/drugs/{drug_id}").json()
    assert any("Hypertension" in i["text_en"] for i in detail["indications"])
    assert any(i["is_off_label"] for i in detail["indications"])
    assert detail["warnings"][0]["severity"] == "boxed"
    assert detail["interactions"][0]["interacting_agent"] == "Simvastatin"
    # unverified dose rows keep the exact placeholder
    for d in detail["dosages"]:
        if not d["is_verified"]:
            assert d["text_en"] == NOT_AVAILABLE
    # record version bumped by edits
    assert detail["record_version"] >= 2


def test_pregnancy_preserves_source_terminology(client, admin_headers):
    drug_id = _drug_id(client, "Warfarin")
    # register a source first
    r = client.post("/api/v1/sources", json={
        "name": "Test Regulatory Label (TEST)", "source_type": "official_label",
        "url": "https://example.org/label", "is_demo": True,
    }, headers=admin_headers)
    source_id = r.json()["id"]

    r = client.put(f"/api/v1/drugs/{drug_id}/pregnancy", json={
        "text_en": "DEMO — source terminology preserved verbatim.",
        "risk_label": "Source-specific label (not FDA A–X)",
        "risk_system": "Source classification system",
        "source_id": source_id,
        "last_verified_date": "2026-01-01",
    }, headers=admin_headers)
    assert r.status_code == 200

    detail = client.get(f"/api/v1/drugs/{drug_id}").json()
    assert detail["pregnancy"]["risk_system"] == "Source classification system"
    assert detail["pregnancy"]["source_id"] == source_id


def test_pregnancy_rejects_unknown_source(client, admin_headers):
    drug_id = _drug_id(client)
    r = client.put(f"/api/v1/drugs/{drug_id}/pregnancy", json={
        "text_en": "x", "source_id": "nonexistent",
    }, headers=admin_headers)
    assert r.status_code == 422


def test_therapeutic_alternatives_management(client, admin_headers):
    enalapril = _drug_id(client, "Enalapril")
    losartan_like = _drug_id(client, "Amlodipine")  # different ingredient
    r = client.post(f"/api/v1/drugs/{enalapril}/alternatives", json={
        "alternative_drug_id": losartan_like,
        "rationale_en": "DEMO — therapeutic alternative example; not a substitution recommendation.",
        "evidence_level": "demo",
    }, headers=admin_headers)
    assert r.status_code == 200

    body = client.get(f"/api/v1/drugs/{enalapril}/alternatives").json()
    assert body["label"] == "Therapeutic Alternative"
    assert any(a["id"] == losartan_like for a in body["items"])

    # cannot add itself
    r = client.post(f"/api/v1/drugs/{enalapril}/alternatives", json={
        "alternative_drug_id": enalapril,
    }, headers=admin_headers)
    assert r.status_code == 422

    r = client.delete(f"/api/v1/drugs/{enalapril}/alternatives/{losartan_like}", headers=admin_headers)
    assert r.status_code == 200


def test_field_level_source_links(client, admin_headers):
    drug_id = _drug_id(client, "Metformin")
    r = client.post("/api/v1/sources", json={
        "name": "Field Source (TEST)", "source_type": "reference", "is_demo": True,
    }, headers=admin_headers)
    source_id = r.json()["id"]

    r = client.post(f"/api/v1/drugs/{drug_id}/content-sources", json={
        "source_id": source_id, "section": "dosage.adult",
        "quote": "Dose text quoted from this source.",
    }, headers=admin_headers)
    assert r.status_code == 200

    r = client.post(f"/api/v1/drugs/{drug_id}/sources", json={
        "source_id": source_id, "section": "record", "note": "record-level link",
    }, headers=admin_headers)
    assert r.status_code == 200

    body = client.get(f"/api/v1/drugs/{drug_id}/sources").json()
    assert body["field_level"][0]["section"] == "dosage.adult"
    assert body["record_level"][0]["section"] == "record"
    assert body["field_level"][0]["source_name"] == "Field Source (TEST)"


def test_translations_workflow(client, admin_headers):
    drug_id = _drug_id(client, "Omeprazole")
    r = client.post("/api/v1/translations", json={
        "entity_type": "drug", "entity_id": drug_id, "field": "overview_en",
        "language": "ar", "original_text": "English original (never overwritten)",
        "translated_text": "ترجمة آلية — تحتاج مراجعة", "status": "machine_translated",
    }, headers=admin_headers)
    assert r.status_code == 200

    listing = client.get("/api/v1/translations", params={"entity_id": drug_id}, headers=admin_headers).json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["status"] == "machine_translated"
    assert item["original_text"] == "English original (never overwritten)"

    r = client.post(f"/api/v1/translations/{item['id']}/approve", headers=admin_headers)
    assert r.status_code == 200
    listing = client.get("/api/v1/translations", params={"entity_id": drug_id}, headers=admin_headers).json()
    assert listing["items"][0]["status"] == "human_reviewed"
    assert listing["items"][0]["reviewed_by"]  # approver recorded


def test_favorites_lifecycle(client, admin_headers):
    drug_id = _drug_id(client, "Furosemide")
    r = client.post("/api/v1/favorites", json={"entity_type": "drug", "entity_id": drug_id},
                    headers=admin_headers)
    assert r.status_code == 200

    body = client.get("/api/v1/favorites", headers=admin_headers).json()
    assert body["total"] == 1
    assert body["items"][0]["label"] == "Furosemide"

    r = client.delete(f"/api/v1/favorites/drug/{drug_id}", headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/v1/favorites", headers=admin_headers).json()["total"] == 0


def test_favorites_unknown_entity_rejected(client, admin_headers):
    r = client.post("/api/v1/favorites", json={"entity_type": "drug", "entity_id": "missing"},
                    headers=admin_headers)
    assert r.status_code == 404


def test_drug_request_workflow(client, admin_headers, public_headers):
    r = client.post("/api/v1/drug-requests", params={
        "name": "Requestedin", "reason": "Not in database yet", "name_ar": "ريكوستدين",
    }, headers=public_headers)
    assert r.status_code == 200

    listing = client.get("/api/v1/drug-requests", headers=admin_headers).json()
    req = next(x for x in listing["items"] if x["requested_name"] == "Requestedin")

    r = client.patch(f"/api/v1/drug-requests/{req['id']}", params={
        "status": "researching", "resolution_notes": "Searching sources",
    }, headers=admin_headers)
    assert r.status_code == 200

    r = client.patch(f"/api/v1/drug-requests/{req['id']}", params={"status": "published"},
                     headers=admin_headers)
    assert r.status_code == 200

    listing = client.get("/api/v1/drug-requests", headers=admin_headers).json()
    req = next(x for x in listing["items"] if x["requested_name"] == "Requestedin")
    assert req["status"] == "published"

    # illegal status rejected
    r = client.patch(f"/api/v1/drug-requests/{req['id']}", params={"status": "bogus"},
                     headers=admin_headers)
    assert r.status_code == 422


def test_monograph_edits_require_permission(client, public_headers):
    drug_id = _drug_id(client)
    r = client.put(f"/api/v1/drugs/{drug_id}/warnings", json={"items": []}, headers=public_headers)
    assert r.status_code == 403
    r = client.put(f"/api/v1/drugs/{drug_id}/pregnancy", json={"text_en": "x"}, headers=public_headers)
    assert r.status_code == 403
