import respx
from httpx import Response


def test_yandex_login_redirects_with_state(client):
    resp = client.get("/api/auth/yandex/login", follow_redirects=False)
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert location.startswith("https://oauth.yandex.ru/authorize")
    assert "state=" in location
    assert "yx_state" in resp.cookies


@respx.mock
def test_yandex_callback_creates_user_and_redirects(client):
    respx.post("https://oauth.yandex.ru/token").mock(
        return_value=Response(200, json={"access_token": "ya-token"})
    )
    respx.get("https://login.yandex.ru/info").mock(
        return_value=Response(
            200,
            json={"id": "yx-123", "default_email": "ya@yandex.ru", "real_name": "Ян Дексов"},
        )
    )
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)

    resp = client.get(
        f"/api/auth/yandex/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 307
    assert "#access_token=" in resp.headers["location"]

    # первый пользователь -> активный админ
    import urllib.parse

    fragment = urllib.parse.urlparse(resp.headers["location"]).fragment
    access = dict(p.split("=", 1) for p in fragment.split("&"))["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.json()["email"] == "ya@yandex.ru"
    assert me.json()["role"] == "admin"


def test_yandex_callback_bad_state_400(client):
    client.cookies.set("yx_state", "expected")
    resp = client.get(
        "/api/auth/yandex/callback?code=abc&state=tampered", follow_redirects=False
    )
    assert resp.status_code == 400


@respx.mock
def test_yandex_links_to_existing_email_account(client):
    client.post(
        "/api/auth/register",
        json={"email": "ya@yandex.ru", "password": "secret123", "name": "Т"},
    )
    respx.post("https://oauth.yandex.ru/token").mock(
        return_value=Response(200, json={"access_token": "ya-token"})
    )
    respx.get("https://login.yandex.ru/info").mock(
        return_value=Response(
            200, json={"id": "yx-777", "default_email": "ya@yandex.ru", "real_name": ""}
        )
    )
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)
    resp = client.get(
        f"/api/auth/yandex/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 307


@respx.mock
def test_blocked_yandex_user_gets_403(client, db_session):
    respx.post("https://oauth.yandex.ru/token").mock(
        return_value=Response(200, json={"access_token": "ya-token"})
    )
    respx.get("https://login.yandex.ru/info").mock(
        return_value=Response(
            200, json={"id": "yx-bad", "default_email": "bad@yandex.ru", "real_name": ""}
        )
    )

    def do_callback():
        login = client.get("/api/auth/yandex/login", follow_redirects=False)
        state = login.cookies["yx_state"]
        client.cookies.set("yx_state", state)
        return client.get(
            f"/api/auth/yandex/callback?code=abc&state={state}", follow_redirects=False
        )

    assert do_callback().status_code == 307  # создан

    from sqlalchemy import select

    from app.auth.models import User

    user = db_session.scalar(select(User).where(User.yandex_id == "yx-bad"))
    user.status = "blocked"
    db_session.commit()

    assert do_callback().status_code == 403
