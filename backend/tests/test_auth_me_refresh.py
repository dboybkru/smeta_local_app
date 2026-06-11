def make_user(client, email="user@test.ru"):
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret123", "name": "Т"},
    )
    assert resp.status_code == 201
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
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


def block_user(db_session, email):
    from sqlalchemy import select

    from app.auth.models import User

    user = db_session.scalar(select(User).where(User.email == email))
    user.status = "blocked"
    db_session.commit()


def test_blocked_user_cannot_refresh(client, db_session):
    make_user(client, email="admin@test.ru")
    tokens = make_user(client, email="bad@test.ru")
    block_user(db_session, "bad@test.ru")
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_blocked_user_cannot_login(client, db_session):
    make_user(client, email="admin@test.ru")
    make_user(client, email="bad@test.ru")
    block_user(db_session, "bad@test.ru")
    resp = client.post(
        "/api/auth/login", json={"email": "bad@test.ru", "password": "secret123"}
    )
    assert resp.status_code == 401
