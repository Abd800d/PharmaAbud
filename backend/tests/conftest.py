"""Shared test fixtures: fresh seeded SQLite database + FastAPI TestClient."""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SECRET_KEY"] = "test-secret-key-for-automated-tests-only"
os.environ["AI_PROVIDER"] = "extractive"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import reset_engine  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "aph_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    get_settings.cache_clear()
    reset_engine()

    from app.db.seed import seed_database
    from app.main import app

    engine = __import__("app.core.db", fromlist=["get_engine"]).get_engine()
    Base.metadata.create_all(engine)
    Session = get_session_factory()
    db = Session()
    try:
        seed_database(db, with_demo=True, create_admin=True)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as c:
        yield c

    reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": "admin@aphdemo.com", "password": "ChangeMe!123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def public_headers(client: TestClient) -> dict:
    resp = client.post("/api/v1/auth/register", json={
        "email": "public@example.com", "password": "PublicPass123", "full_name": "Public User",
    })
    assert resp.status_code == 200, resp.text
    resp = client.post("/api/v1/auth/login", json={"email": "public@example.com", "password": "PublicPass123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
