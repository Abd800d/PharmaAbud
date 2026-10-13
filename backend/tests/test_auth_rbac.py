"""Authentication & RBAC tests (§28, §45, §77)."""
from __future__ import annotations


def test_register_login_me(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "pharmacist@example.com", "password": "SecurePass123", "full_name": "Dr Test",
        "preferred_language": "ar",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "pharmacist@example.com"
    assert "public_user" in [role["code"] for role in body["roles"]]

    r = client.post("/api/v1/auth/login", json={"email": "pharmacist@example.com", "password": "SecurePass123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "pharmacist@example.com"
    assert "drug.read" in r.json()["permissions"]


def test_invalid_login_rejected(client):
    r = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_unauthenticated_access_rejected(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    r = client.post("/api/v1/drugs", json={"generic_name_en": "X"})
    assert r.status_code == 401


def test_rbac_privilege_escalation_blocked(client, public_headers):
    """A public user must not create drugs or manage users (§77)."""
    r = client.post("/api/v1/drugs", json={"generic_name_en": "ShouldFail"}, headers=public_headers)
    assert r.status_code == 403
    r = client.get("/api/v1/users", headers=public_headers)
    assert r.status_code == 403
    r = client.post("/api/v1/drugs/x/verify", json={"new_status": "verified"}, headers=public_headers)
    assert r.status_code == 403


def test_admin_can_manage_roles(client, admin_headers):
    r = client.post("/api/v1/auth/register", json={"email": "reviewer@example.com", "password": "ReviewerPass1"})
    user_id = r.json()["id"]
    r = client.put(f"/api/v1/users/{user_id}/roles", json={"role_codes": ["pharmacist_reviewer"]},
                   headers=admin_headers)
    assert r.status_code == 200

    r = client.post("/api/v1/auth/login", json={"email": "reviewer@example.com", "password": "ReviewerPass1"})
    token = r.json()["access_token"]
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    perms = r.json()["permissions"]
    assert "drug.verify" in perms
    assert "user.manage" not in perms


def test_password_hashed_not_stored_plain(client, admin_headers):
    r = client.get("/api/v1/users", headers=admin_headers)
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert "password" not in item
        assert "ChangeMe!123" not in str(item)


def test_refresh_token_flow(client):
    client.post("/api/v1/auth/register", json={"email": "refresh@example.com", "password": "RefreshPass1"})
    r = client.post("/api/v1/auth/login", json={"email": "refresh@example.com", "password": "RefreshPass1"})
    refresh = r.json()["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_bad_token_rejected(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_roles_seeded_per_spec(client, admin_headers):
    r = client.get("/api/v1/users/roles", headers=admin_headers)
    codes = {role["code"] for role in r.json()}
    assert {
        "public_user", "pharmacist_reviewer", "data_manager",
        "image_reviewer", "translator", "administrator", "super_administrator",
    } <= codes
