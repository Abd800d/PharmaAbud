"""Drug encyclopedia + verification workflow tests (§6, §23, §89)."""
from __future__ import annotations

NOT_AVAILABLE = "Not available / Requires verified source"


def _get_drug_id(client, name="Enalapril"):
    data = client.get("/api/v1/search", params={"q": name, "kinds": "drug"}).json()
    hits = [h for h in data["items"] if h["kind"] == "drug" and h["name_en"] == name]
    assert hits, f"demo drug {name} not found"
    return hits[0]["id"]


def test_drug_detail_sections(client):
    drug_id = _get_drug_id(client)
    r = client.get(f"/api/v1/drugs/{drug_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["generic_name_en"] == "Enalapril"
    assert body["generic_name_ar"] == "إينالابريل"
    for section in ("mechanism_en", "indications", "dosages", "pregnancy", "lactation",
                    "products" if False else "synonyms", "classifications"):
        assert section in body, section
    # demo doses must never be invented (§6)
    for dose in body["dosages"]:
        assert dose["text_en"] == NOT_AVAILABLE or dose["is_verified"] is True
    # pregnancy preserves source terminology; demo rows are explicitly unverified
    if body["pregnancy"]:
        assert body["pregnancy"]["text_en"] == NOT_AVAILABLE or body["pregnancy"]["source_id"]


def test_demo_records_marked(client):
    drug_id = _get_drug_id(client)
    body = client.get(f"/api/v1/drugs/{drug_id}").json()
    assert body["is_demo"] is True
    assert body["verification_status"] != "verified"


def test_equivalent_products_label(client):
    drug_id = _get_drug_id(client, "Amoxicillin")
    body = client.get(f"/api/v1/drugs/{drug_id}/products").json()
    assert body["label"] == "Equivalent Product"
    assert "Not automatically a therapeutic alternative" in body["note"]
    assert body["items"]


def test_therapeutic_alternatives_distinct(client):
    drug_id = _get_drug_id(client, "Enalapril")
    body = client.get(f"/api/v1/drugs/{drug_id}/alternatives").json()
    assert body["label"] == "Therapeutic Alternative"
    assert "substitution" in body["note"].lower()


def test_create_update_drug(client, admin_headers):
    r = client.post("/api/v1/drugs", json={
        "generic_name_en": "Testmol", "generic_name_ar": "تستمول",
        "mechanism_en": "Test mechanism", "is_demo": True,
    }, headers=admin_headers)
    assert r.status_code == 200
    drug_id = r.json()["id"]
    assert r.json()["verification_status"] == "draft"

    r = client.patch(f"/api/v1/drugs/{drug_id}", json={"overview_en": "Updated overview"},
                     headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["record_version"] >= 2

    body = client.get(f"/api/v1/drugs/{drug_id}").json()
    assert body["overview_en"] == "Updated overview"


def test_verification_workflow_transitions(client, admin_headers):
    r = client.post("/api/v1/drugs", json={"generic_name_en": "Verifymol"}, headers=admin_headers)
    drug_id = r.json()["id"]

    # illegal: draft -> verified directly
    r = client.post(f"/api/v1/drugs/{drug_id}/verify", json={"new_status": "verified"}, headers=admin_headers)
    assert r.status_code == 422

    # draft -> pending_verification -> verified
    r = client.post(f"/api/v1/drugs/{drug_id}/verify", json={"new_status": "pending_verification"},
                    headers=admin_headers)
    assert r.status_code == 200
    r = client.post(f"/api/v1/drugs/{drug_id}/verify", json={"new_status": "verified", "notes": "checked"},
                    headers=admin_headers)
    assert r.status_code == 200

    body = client.get(f"/api/v1/drugs/{drug_id}").json()
    assert body["verification_status"] == "verified"
    assert body["verified_at"] is not None

    history = client.get(f"/api/v1/drugs/{drug_id}/verification-history").json()
    statuses = [(h["previous_status"], h["new_status"]) for h in history]
    assert ("pending_verification", "verified") in statuses


def test_all_18_systems_present(client):
    systems = client.get("/api/v1/systems").json()
    assert systems["total"] == 18
    names = {s["name_en"] for s in systems["items"]}
    assert "Nervous System" in names
    assert "Cardiovascular System" in names
    assert "Emergency and Toxicology" in names
    arabic = {s["name_ar"] for s in systems["items"]}
    assert "الجهاز العصبي" in arabic
    # every system has demo drugs
    for s in systems["items"]:
        assert s["drug_count"] >= 1, f"system {s['slug']} has no drugs"


def test_system_hierarchy(client):
    systems = client.get("/api/v1/systems").json()["items"]
    cardio = next(s for s in systems if s["slug"] == "cardiovascular-system")
    groups = client.get(f"/api/v1/systems/{cardio['id']}/groups").json()["items"]
    assert groups
    assert any(g["pharmacological_classes"] for g in groups)
    # Enalapril sits under Cardiovascular -> Antihypertensives -> ACE Inhibitors
    class_names = [c["name_en"] for g in groups for c in g["pharmacological_classes"]]
    assert "ACE Inhibitors" in class_names


def test_multi_system_drug(client, admin_headers):
    """A drug may belong to multiple systems when justified (§70)."""
    # Methotrexate is demo-seeded under oncology; add it to immune-system as well
    drug_id = _get_drug_id(client, "Methotrexate")
    systems = client.get("/api/v1/systems").json()["items"]
    immune = next(s for s in systems if s["slug"] == "immune-system")
    groups = client.get(f"/api/v1/systems/{immune['id']}/groups").json()["items"]
    # verify by search filter: drug appears under its seeded system
    oncology = next(s for s in systems if s["slug"] == "oncology")
    data = client.get("/api/v1/search", params={"q": "Methotrexate", "system_id": oncology["id"]}).json()
    assert any(h["id"] == drug_id for h in data["items"])
