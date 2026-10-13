"""Search engine tests (§9, §75): exact, partial, typo, Arabic, barcode, no-result."""
from __future__ import annotations


def _search(client, q, **params):
    r = client.get("/api/v1/search", params={"q": q, **params})
    assert r.status_code == 200
    return r.json()


def test_exact_generic_match_ranked_first(client):
    data = _search(client, "Amoxicillin")
    assert data["total"] > 0
    first = data["items"][0]
    assert first["name_en"] == "Amoxicillin"
    assert first["kind"] == "drug"
    assert first["match_type"] in ("exact_generic", "exact")


def test_exact_brand_match(client):
    # demo products are named "DemoBrand <Generic>"; search a brand
    data = _search(client, "DemoBrand")
    assert data["total"] > 0
    assert any(h["kind"] == "product" for h in data["items"])


def test_arabic_search(client):
    data = _search(client, "أموكسيسيلين")
    assert data["total"] > 0
    assert any(h["name_en"] == "Amoxicillin" for h in data["items"])


def test_arabic_prefix_search(client):
    data = _search(client, "أموكس")
    assert data["total"] > 0
    assert any(h["name_en"] == "Amoxicillin" for h in data["items"])


def test_typo_fuzzy_search(client):
    for typo in ("amoxcillin", "amoxilin", "amoxicilin"):
        data = _search(client, typo)
        assert data["total"] > 0, f"typo '{typo}' produced no results"
        assert any(h["name_en"] == "Amoxicillin" for h in data["items"]), typo


def test_prefix_search(client):
    data = _search(client, "amox")
    assert data["total"] > 0
    assert any(h["name_en"] == "Amoxicillin" for h in data["items"])


def test_barcode_search(client):
    # find a demo product barcode first
    products = client.get("/api/v1/products", params={"q": "DemoBrand", "limit": 5}).json()
    assert products["items"], "expected demo products"
    barcode = products["items"][0]["barcode"]
    assert barcode
    data = _search(client, barcode)
    assert data["total"] > 0
    assert data["items"][0]["match_type"] == "barcode"


def test_manufacturer_and_form_filters(client):
    forms = client.get("/api/v1/dosage-forms").json()["items"]
    tablet = next(f for f in forms if f["slug"] == "tablet")
    data = _search(client, "DemoBrand", dosage_form="tablet")
    assert data["total"] > 0
    for hit in data["items"]:
        if hit["kind"] == "product":
            assert "tablet" in hit["subtitle"].lower()


def test_no_result_gives_suggestions(client):
    data = _search(client, "amoxcyllnqqqzz")
    assert data["total"] == 0
    assert isinstance(data["suggestions"], list)


def test_distinguish_generic_vs_product(client):
    data = _search(client, "Amoxicillin")
    kinds = {h["kind"] for h in data["items"]}
    assert "drug" in kinds
    # generic and commercial results must be typed differently (§10)
    for h in data["items"]:
        assert h["kind"] in ("drug", "product")


def test_suggest_endpoint(client):
    r = client.get("/api/v1/search/suggest", params={"q": "Enal"})
    assert r.status_code == 200
    assert any("Enalapril" in s["text"] for s in r.json()["suggestions"])


def test_combination_product_searchable(client):
    data = _search(client, "Clavulanate")
    assert data["total"] > 0


def test_search_stats_aggregated_no_user_ids(client):
    _search(client, "Amoxicillin")
    r = client.get("/api/v1/admin/search-analytics", headers={"Authorization": "Bearer " + _admin(client)})
    assert r.status_code == 200
    body = r.json()
    assert "most_searched" in body
    for term in body["most_searched"]:
        assert set(term.keys()) <= {"term", "hits", "language"}


def _admin(client) -> str:
    r = client.post("/api/v1/auth/login", json={"email": "admin@aphdemo.com", "password": "ChangeMe!123"})
    return r.json()["access_token"]
