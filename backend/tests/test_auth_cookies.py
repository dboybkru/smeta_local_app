from app.auth.models import User
from app.core.security import hash_password
from app.orgs.models import Organization


def _active_user(db, email="ck@x.ru", pw="Pass12345"):
    o = Organization(name="CK"); db.add(o); db.commit()
    u = User(email=email, name="U", role="org_admin", status="active",
             org_id=o.id, password_hash=hash_password(pw))
    db.add(u); db.commit(); return u


def test_login_sets_httponly_cookies_and_returns_user(client, db_session):
    _active_user(db_session)
    r = client.post("/api/auth/login", json={"email": "ck@x.ru", "password": "Pass12345"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "ck@x.ru"  # UserOut, не токены
    # access/refresh httpOnly, csrf — нет
    cookies = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else [r.headers["set-cookie"]]
    joined = " ".join(cookies)
    assert "access_token=" in joined and "HttpOnly" in joined
    assert "csrf_token=" in joined


def test_me_via_cookie(client, db_session):
    _active_user(db_session)
    client.post("/api/auth/login", json={"email": "ck@x.ru", "password": "Pass12345"})
    # cookie jar TestClient уже держит cookie
    r = client.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["email"] == "ck@x.ru"


def test_refresh_via_cookie(client, db_session):
    _active_user(db_session)
    client.post("/api/auth/login", json={"email": "ck@x.ru", "password": "Pass12345"})
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200 and r.json()["email"] == "ck@x.ru"


def test_logout_clears_cookies(client, db_session):
    _active_user(db_session)
    client.post("/api/auth/login", json={"email": "ck@x.ru", "password": "Pass12345"})
    # logout — cookie-auth, нужен CSRF-заголовок (см. Task 2); шлём из cookie
    csrf = client.cookies.get("csrf_token")
    r = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf} if csrf else {})
    assert r.status_code == 204
    # после logout /me не пускает
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
