"""
Тесты для Яндекс OAuth с кредами из БД (app_settings) и без них.
Проверяют env-фолбэк и работу _yandex_creds.
"""

import respx
from httpx import Response

from app.auth.models import User
from app.core.config import settings
from app.core.security import create_access_token
from app.settings import service as settings_service
from app.settings.router import YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET


def _admin(db):
    u = User(email="adm_yxdb@x.ru", name="A", role="org_admin", status="active")
    db.add(u)
    db.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


# ---------------------------------------------------------------------------
# Группа 1: креды из БД
# ---------------------------------------------------------------------------


def test_auth_config_yandex_enabled_with_db_creds(client, db_session):
    """GET /api/auth/config → yandex_enabled=true если client_id есть в БД."""
    settings_service.set_secret(db_session, YANDEX_CLIENT_ID, "db-client-id")
    settings_service.set_secret(db_session, YANDEX_CLIENT_SECRET, "db-secret")
    r = client.get("/api/auth/config")
    assert r.status_code == 200
    assert r.json()["yandex_enabled"] is True


def test_yandex_login_redirect_contains_db_client_id(client, db_session):
    """GET /yandex/login → редирект содержит client_id из БД."""
    settings_service.set_secret(db_session, YANDEX_CLIENT_ID, "db-client-id-42")
    settings_service.set_secret(db_session, YANDEX_CLIENT_SECRET, "db-secret-42")
    resp = client.get("/api/auth/yandex/login", follow_redirects=False)
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "db-client-id-42" in location
    assert location.startswith("https://oauth.yandex.ru/authorize")


@respx.mock
def test_yandex_callback_uses_db_creds(client, db_session):
    """callback exchange_code вызывается с DB-кредами."""
    settings_service.set_secret(db_session, YANDEX_CLIENT_ID, "db-cid")
    settings_service.set_secret(db_session, YANDEX_CLIENT_SECRET, "db-csec")

    # Перехватываем POST к token endpoint и проверяем, что переданы DB-creds
    seen = {}

    def token_handler(request):
        body = dict(p.split("=") for p in request.content.decode().split("&"))
        seen["client_id"] = body.get("client_id", "")
        seen["client_secret"] = body.get("client_secret", "")
        return Response(200, json={"access_token": "ya-token"})

    respx.post("https://oauth.yandex.ru/token").mock(side_effect=token_handler)
    respx.get("https://login.yandex.ru/info").mock(
        return_value=Response(
            200,
            json={"id": "yx-db1", "default_email": "dbuser@ya.ru", "real_name": "DB User"},
        )
    )
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)
    resp = client.get(
        f"/api/auth/yandex/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 307
    assert seen.get("client_id") == "db-cid"
    assert seen.get("client_secret") == "db-csec"


# ---------------------------------------------------------------------------
# Группа 2: ни DB ни env → 503 / yandex_enabled=false
# ---------------------------------------------------------------------------


def test_auth_config_yandex_disabled_without_creds(client, db_session, monkeypatch):
    """Без DB-кредов и без env → yandex_enabled=false."""
    monkeypatch.setattr(settings, "yandex_client_id", "")
    monkeypatch.setattr(settings, "yandex_client_secret", "")
    r = client.get("/api/auth/config")
    assert r.status_code == 200
    assert r.json()["yandex_enabled"] is False


def test_yandex_login_503_without_creds(client, db_session, monkeypatch):
    """Без кредов → 503."""
    monkeypatch.setattr(settings, "yandex_client_id", "")
    monkeypatch.setattr(settings, "yandex_client_secret", "")
    resp = client.get("/api/auth/yandex/login", follow_redirects=False)
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Группа 3: env-фолбэк работает (DB пуста, env заполнен)
# ---------------------------------------------------------------------------


def test_auth_config_uses_env_fallback(client, db_session, monkeypatch):
    """DB пуста, но env заполнен → yandex_enabled=true."""
    monkeypatch.setattr(settings, "yandex_client_id", "env-fallback-id")
    monkeypatch.setattr(settings, "yandex_client_secret", "env-fallback-secret")
    r = client.get("/api/auth/config")
    assert r.status_code == 200
    assert r.json()["yandex_enabled"] is True


def test_yandex_login_env_fallback_in_location(client, db_session, monkeypatch):
    """Редирект содержит client_id из env при пустой DB."""
    monkeypatch.setattr(settings, "yandex_client_id", "env-id-xyz")
    monkeypatch.setattr(settings, "yandex_client_secret", "env-sec")
    resp = client.get("/api/auth/yandex/login", follow_redirects=False)
    assert resp.status_code == 307
    assert "env-id-xyz" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Группа 4: DB-кред перекрывает env
# ---------------------------------------------------------------------------


def test_db_creds_override_env(client, db_session, monkeypatch):
    """DB-кред имеет приоритет над env."""
    monkeypatch.setattr(settings, "yandex_client_id", "env-client-id")
    monkeypatch.setattr(settings, "yandex_client_secret", "env-secret")
    settings_service.set_secret(db_session, YANDEX_CLIENT_ID, "db-priority-id")
    settings_service.set_secret(db_session, YANDEX_CLIENT_SECRET, "db-priority-secret")

    resp = client.get("/api/auth/yandex/login", follow_redirects=False)
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "db-priority-id" in location
    assert "env-client-id" not in location
