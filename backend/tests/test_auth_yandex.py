import pytest
import respx
from httpx import Response


@pytest.fixture(autouse=True)
def _yandex_client_id(monkeypatch):
    """Все тесты в этом модуле требуют непустого yandex_client_id."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "yandex_client_id", "test-yandex-client-id")
    monkeypatch.setattr(settings, "yandex_client_secret", "test-yandex-secret")


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
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "/auth/callback" in location
    assert "#" not in location
    assert "access_token" in resp.cookies

    # первый пользователь -> активный админ
    me = client.get("/api/auth/me")
    assert me.json()["email"] == "ya@yandex.ru"
    assert me.json()["role"] == "org_admin"


@respx.mock
def test_yandex_callback_sets_cookies_no_fragment(client):
    """Callback ставит cookie с токеном и редиректит БЕЗ fragment (#)."""
    respx.post("https://oauth.yandex.ru/token").mock(
        return_value=Response(200, json={"access_token": "ya-token"})
    )
    respx.get("https://login.yandex.ru/info").mock(
        return_value=Response(
            200,
            json={"id": "yx-456", "default_email": "cookie@yandex.ru", "real_name": "Куки Тест"},
        )
    )
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)

    resp = client.get(
        f"/api/auth/yandex/callback?code=xyz&state={state}", follow_redirects=False
    )

    # редирект без фрагмента
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "/auth/callback" in location
    assert "#" not in location

    # access_token должен прийти в Set-Cookie
    assert "access_token" in resp.cookies


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


@respx.mock
def test_yandex_error_returns_502(client):
    respx.post("https://oauth.yandex.ru/token").mock(return_value=Response(400))
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)
    resp = client.get(
        f"/api/auth/yandex/callback?code=expired&state={state}", follow_redirects=False
    )
    assert resp.status_code == 502


@respx.mock
def test_yandex_links_by_email_case_insensitive(client, db_session):
    client.post(
        "/api/auth/register",
        json={"email": "ya@yandex.ru", "password": "secret123", "name": "Т"},
    )
    respx.post("https://oauth.yandex.ru/token").mock(
        return_value=Response(200, json={"access_token": "ya-token"})
    )
    respx.get("https://login.yandex.ru/info").mock(
        return_value=Response(
            200, json={"id": "yx-888", "default_email": "YA@yandex.ru", "real_name": ""}
        )
    )
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)
    resp = client.get(
        f"/api/auth/yandex/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 307
    # не должен создаться второй аккаунт
    from sqlalchemy import func, select

    from app.auth.models import User

    assert db_session.scalar(select(func.count()).select_from(User)) == 1


@respx.mock
def test_yandex_network_failure_returns_503(client):
    import httpx as _httpx

    respx.post("https://oauth.yandex.ru/token").mock(
        side_effect=_httpx.ConnectError("boom")
    )
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)
    resp = client.get(
        f"/api/auth/yandex/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 503
