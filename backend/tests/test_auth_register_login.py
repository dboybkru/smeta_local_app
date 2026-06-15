def register(client, email="user@test.ru", password="secret123", name="Тест"):
    return client.post(
        "/api/auth/register", json={"email": email, "password": password, "name": name}
    )


def test_first_user_becomes_active_admin(client):
    resp = register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "org_admin"
    assert body["status"] == "active"


def test_second_user_is_pending_estimator(client):
    register(client, email="first@test.ru")
    resp = register(client, email="second@test.ru")
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "estimator"
    assert body["status"] == "pending"


def test_duplicate_email_rejected(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 409


def test_login_returns_token_pair(client):
    register(client)
    resp = client.post(
        "/api/auth/login", json={"email": "user@test.ru", "password": "secret123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_401(client):
    register(client)
    resp = client.post("/api/auth/login", json={"email": "user@test.ru", "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_email_401(client):
    resp = client.post("/api/auth/login", json={"email": "ghost@test.ru", "password": "x"})
    assert resp.status_code == 401


def test_login_user_without_password_rejected(client, db_session):
    from app.auth.models import User

    db_session.add(User(email="ya-only@test.ru", yandex_id="yx-1", password_hash=None))
    db_session.commit()
    resp = client.post(
        "/api/auth/login", json={"email": "ya-only@test.ru", "password": "anything"}
    )
    assert resp.status_code == 401


def test_login_email_case_insensitive(client):
    register(client, email="user@test.ru")
    resp = client.post(
        "/api/auth/login", json={"email": "USER@test.ru", "password": "secret123"}
    )
    assert resp.status_code == 200


def test_register_duplicate_email_case_insensitive(client):
    register(client, email="user@test.ru")
    resp = register(client, email="User@test.ru")
    assert resp.status_code == 409
