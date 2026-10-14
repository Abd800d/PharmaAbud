"""Record links: Equivalent Products (§11) + duplicate-link review (§16, §111)."""
from __future__ import annotations


def _ids(client, headers):
    listing = client.get("/api/v1/products", params={"limit": 30}, headers=headers).json()
    items = listing["items"]
    return items[0]["id"], items[1]["id"]


def test_equivalent_link_requires_why_and_starts_pending(client, admin_headers):
    a, b = _ids(client, admin_headers)

    # 'why' is mandatory (§111)
    missing_why = client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": b},
        headers=admin_headers,
    )
    assert missing_why.status_code == 422

    resp = client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": b, "why": "Same active ingredient + strength + form (DEMO check)"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "Equivalent Product" in resp.json()["message"]
    assert "pending human review" in resp.json()["message"]

    listing = client.get(f"/api/v1/products/{a}/equivalents", headers=admin_headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["label"] == "Equivalent Product"  # exact label (§11)
    assert "NOT" in body["note"] and "interchangeable" in body["note"]
    assert len(body["items"]) == 1
    link = body["items"][0]
    # §111 metadata present
    for key in ("linked_by", "why", "checked_by", "approved_by", "approval_date"):
        assert key in link
    assert link["status"] == "pending"
    assert link["linked_by"]  # Linked By (§111) is set to the creating user
    assert link["why"].startswith("Same active ingredient")
    assert link["checked_by"] is None and link["approved_by"] is None

    # never auto-approved (§16) — still pending until human review
    assert link["approval_date"] is None


def test_equivalent_self_link_and_duplicates_rejected(client, admin_headers):
    a, b = _ids(client, admin_headers)
    self_link = client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": a, "why": "self"},
        headers=admin_headers,
    )
    assert self_link.status_code == 422

    client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": b, "why": "basis"},
        headers=admin_headers,
    )
    dup = client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": b, "why": "basis again"},
        headers=admin_headers,
    )
    assert dup.status_code == 422  # unique link

    # order-independent: b→a is the same link
    rev = client.post(
        f"/api/v1/products/{b}/equivalents",
        params={"target_product_id": a, "why": "reverse"},
        headers=admin_headers,
    )
    assert rev.status_code == 422


def test_link_review_records_section111_metadata(client, admin_headers):
    a, b = _ids(client, admin_headers)
    client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": b, "why": "Same ingredient (review test)"},
        headers=admin_headers,
    )
    link_id = client.get(f"/api/v1/products/{a}/equivalents", headers=admin_headers).json()["items"][0]["id"]

    # invalid decision → 422
    bad = client.post(f"/api/v1/record-links/{link_id}/review",
                      params={"decision": "maybe"}, headers=admin_headers)
    assert bad.status_code == 422

    resp = client.post(f"/api/v1/record-links/{link_id}/review",
                       params={"decision": "approve", "notes": "checked against demo source"},
                       headers=admin_headers)
    assert resp.status_code == 200

    link = client.get(f"/api/v1/products/{a}/equivalents", headers=admin_headers).json()["items"][0]
    assert link["status"] == "approved"
    assert link["checked_by"] is not None        # Checked By (§111)
    assert link["approved_by"] is not None       # Approved By (§111)
    assert link["approval_date"] is not None     # Approval Date (§111)
    assert "checked against demo source" in link["notes"]


def test_record_links_review_queue(client, admin_headers):
    a, b = _ids(client, admin_headers)
    client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": b, "why": "queue test"},
        headers=admin_headers,
    )
    queue = client.get("/api/v1/record-links", params={"status": "pending"}, headers=admin_headers)
    assert queue.status_code == 200
    body = queue.json()
    assert body["items"], "expected a pending link in the review queue"
    assert "Never auto-merged" in body["policy"]
    assert "Linked by / Why / Checked By / Approved By / Approval Date" in body["policy"]

    # reject flow
    link_id = body["items"][0]["id"]
    client.post(f"/api/v1/record-links/{link_id}/review",
                params={"decision": "reject"}, headers=admin_headers)
    after = client.get(f"/api/v1/record-links", params={"status": "rejected"}, headers=admin_headers)
    assert any(i["id"] == link_id for i in after.json()["items"])
    rejected = next(i for i in after.json()["items"] if i["id"] == link_id)
    assert rejected["approved_by"] is None and rejected["approval_date"] is None

    # delete removes it
    gone = client.delete(f"/api/v1/record-links/{link_id}", headers=admin_headers)
    assert gone.status_code == 200
    still = client.get("/api/v1/record-links", params={"status": "rejected"}, headers=admin_headers)
    assert all(i["id"] != link_id for i in still.json()["items"])


def test_duplicates_endpoint_includes_link_metadata(client, admin_headers):
    a, b = _ids(client, admin_headers)
    client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": b, "why": "shown in duplicates"},
        headers=admin_headers,
    )
    resp = client.get(f"/api/v1/products/{a}/duplicates", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "never auto-merged" in body["note"]
    assert len(body["links"]) >= 1
    for key in ("linked_by", "why", "checked_by", "approved_by", "approval_date"):
        assert key in body["links"][0]
    assert body["links"][0]["label"] in ("Equivalent Product", "Duplicate Candidate")


def test_record_links_permissions(client, admin_headers):
    a, b = _ids(client, admin_headers)
    # anonymous cannot review or create
    anon_create = client.post(
        f"/api/v1/products/{a}/equivalents",
        params={"target_product_id": b, "why": "anon"},
    )
    assert anon_create.status_code in (401, 403)
    anon_review = client.post("/api/v1/record-links/whatever/review", params={"decision": "approve"})
    assert anon_review.status_code in (401, 403)
    anon_queue = client.get("/api/v1/record-links")
    assert anon_queue.status_code in (401, 403)

    # reading equivalents is public (like product pages)
    pub = client.get(f"/api/v1/products/{a}/equivalents")
    assert pub.status_code == 200
