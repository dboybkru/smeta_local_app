def make_user(client, email):
    resp = client.post(
        "/api/auth/register", json={"email": email, "password": "secret123", "name": "Т"}
    )
    assert resp.status_code == 201
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
    return resp.json()


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_admin_lists_users(client):
    admin = make_user(client, "admin@test.ru")
    make_user(client, "second@test.ru")
    resp = client.get("/api/admin/users", headers=auth(admin))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_non_admin_cannot_list_users(client):
    make_user(client, "admin@test.ru")
    second = make_user(client, "second@test.ru")
    resp = client.get("/api/admin/users", headers=auth(second))
    assert resp.status_code == 403


def test_admin_approves_pending_user(client):
    admin = make_user(client, "admin@test.ru")
    make_user(client, "second@test.ru")
    users = client.get("/api/admin/users", headers=auth(admin)).json()
    pending_id = next(u["id"] for u in users if u["status"] == "pending")
    resp = client.post(
        f"/api/admin/users/{pending_id}/status",
        json={"status": "active"},
        headers=auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_status_change_unknown_user_404(client):
    admin = make_user(client, "admin@test.ru")
    resp = client.post(
        "/api/admin/users/999/status", json={"status": "active"}, headers=auth(admin)
    )
    assert resp.status_code == 404


def test_invalid_status_rejected(client):
    admin = make_user(client, "admin@test.ru")
    resp = client.post(
        "/api/admin/users/1/status", json={"status": "superuser"}, headers=auth(admin)
    )
    assert resp.status_code == 422


def test_admin_cannot_block_self(client):
    admin = make_user(client, "admin@test.ru")
    me = client.get("/api/auth/me", headers=auth(admin)).json()
    resp = client.post(
        f"/api/admin/users/{me['id']}/status", json={"status": "blocked"}, headers=auth(admin)
    )
    assert resp.status_code == 400


def test_admin_blocks_other_user(client):
    admin = make_user(client, "admin@test.ru")
    make_user(client, "second@test.ru")
    users = client.get("/api/admin/users", headers=auth(admin)).json()
    other_id = next(u["id"] for u in users if u["email"] == "second@test.ru")
    resp = client.post(
        f"/api/admin/users/{other_id}/status", json={"status": "blocked"}, headers=auth(admin)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"
