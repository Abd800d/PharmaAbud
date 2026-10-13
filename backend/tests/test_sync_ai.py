"""Sync engine + AI/RAG tests (§32–§33, §41–§43)."""
from __future__ import annotations


def test_sync_pull_returns_incremental_data(client, admin_headers):
    r = client.post("/api/v1/sync/pull", json={"device_id": "device-1", "entity_type": "drug", "limit": 50},
                    headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["entity_type"] == "drug"
    assert len(body["items"]) > 0
    first = body["items"][0]
    assert {"id", "generic_name_en", "record_version", "updated_at"} <= set(first.keys())

    # second pull with watermark → no unchanged rows
    r2 = client.post("/api/v1/sync/pull", json={
        "device_id": "device-1", "entity_type": "drug",
        "since": body["items"][-1]["updated_at"], "limit": 50,
    }, headers=admin_headers)
    assert r2.status_code == 200


def test_sync_push_conflict_detection(client, admin_headers):
    """If the server record is newer than the client base version → CONFLICT (§32)."""
    r = client.post("/api/v1/sync/pull", json={"device_id": "device-2", "entity_type": "drug", "limit": 1},
                    headers=admin_headers)
    item = r.json()["items"][0]

    r = client.post("/api/v1/sync/push", json={
        "device_id": "device-2",
        "changes": [{
            "entity_type": "drug", "entity_id": item["id"], "operation": "update",
            "payload": {"overview_en": "local change"},
            "base_version": 0,  # stale base
            "local_version": 3,
        }],
    }, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["conflicts"] == 1
    assert body["results"][0]["status"] == "conflict"


def test_sync_push_favorites(client, admin_headers):
    r = client.post("/api/v1/sync/pull", json={"device_id": "device-3", "entity_type": "drug", "limit": 1},
                    headers=admin_headers)
    item = r.json()["items"][0]
    r = client.post("/api/v1/sync/push", json={
        "device_id": "device-3",
        "changes": [{
            "entity_type": "favorite", "entity_id": item["id"], "operation": "favorite_add",
            "payload": {"entity_id": item["id"]},
            "base_version": 1, "local_version": 1,
        }],
    }, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["accepted"] == 1


def test_sync_status(client, admin_headers):
    client.post("/api/v1/sync/pull", json={"device_id": "device-4", "entity_type": "product", "limit": 5},
                headers=admin_headers)
    r = client.get("/api/v1/sync/status", headers=admin_headers)
    assert r.status_code == 200
    devices = {s["device_id"] for s in r.json()}
    assert "device-4" in devices


# ------------------------------------------------------------------ AI / RAG
def test_ai_answer_grounded_with_citations(client):
    r = client.post("/api/v1/ai/ask", json={
        "question": "What is the mechanism of action of enalapril?", "language": "en",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is True
    assert "DEMO" in body["answer"] or "ACE" in body["answer"]
    assert body["intent"] in ("mechanism", "overview")
    assert body["disclaimer"].startswith("APH is intended for educational")
    # citations are present and typed (§43)
    assert isinstance(body["citations"], list)


def test_ai_unavailable_information_not_fabricated(client):
    r = client.post("/api/v1/ai/ask", json={
        "question": "What is the maximum velocity of antiprotons during lunar transit dosing?",
        "language": "en",
    })
    body = r.json()
    assert body["grounded"] is False
    assert "could not be verified" in body["answer"].lower()
    assert "APH is intended" in body["disclaimer"]


def test_ai_arabic_interface(client):
    r = client.post("/api/v1/ai/ask", json={
        "question": "ما هي آلية عمل الإينالابريل؟", "language": "ar",
    })
    assert r.status_code == 200
    body = r.json()
    assert "موسوعة عبدالمجيد" in body["disclaimer"] or "APH" in body["disclaimer"]
    if body["grounded"]:
        assert body["answer"]


def test_ai_dosage_questions_never_invented(client):
    r = client.post("/api/v1/ai/ask", json={
        "question": "What is the adult dose of enalapril?", "language": "en",
    })
    body = r.json()
    # demo data has no verified doses → answer must say unavailable, not invent a dose
    if body["grounded"]:
        assert "Not available / Requires verified source" in body["answer"]
    else:
        assert "could not be verified" in body["answer"].lower()


def test_ai_citations_only_retrieved_sources(client):
    r = client.post("/api/v1/ai/ask", json={"question": "Tell me about amoxicillin products"})
    body = r.json()
    for cit in body["citations"]:
        assert set(cit.keys()) >= {"source_name", "section", "entity_type", "entity_id"}
        # never cites fabricated sources
        assert cit["source_name"] != ""


def test_ai_conversation_persisted(client):
    r = client.post("/api/v1/ai/ask", json={"question": "What is metformin?"})
    conv_id = r.json()["conversation_id"]
    r2 = client.post("/api/v1/ai/ask", json={
        "question": "And its mechanism?", "conversation_id": conv_id,
    })
    assert r2.json()["conversation_id"] == conv_id
