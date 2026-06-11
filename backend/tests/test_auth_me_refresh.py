def make_user(client, email="user@test.ru"):
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret123", "name": "Т"},
    )
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    return resp.json()


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_me_returns_current_user(client):
    tokens = make_user(client)
    resp = client.get("/api/auth/me", headers=auth(tokens))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@test.ru"


def test_me_without_token_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_garbage_token_401(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_refresh_returns_new_pair(client):
    tokens = make_user(client)
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_refresh_rejects_access_token(client):
    tokens = make_user(client)
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_pending_user_can_see_me(client):
    make_user(client, email="admin@test.ru")  # первый - админ
    tokens = make_user(client, email="second@test.ru")  # pending
    resp = client.get("/api/auth/me", headers=auth(tokens))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
