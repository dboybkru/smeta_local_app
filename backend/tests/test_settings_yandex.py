"""
Тесты для GET/PUT /api/settings/yandex.
Повторяют паттерн test_settings.py (DaData).
"""

from app.auth.models import User
from app.core.security import create_access_token
from app.settings import service as settings_service
from app.settings.router import YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET


def _admin(db):
    u = User(email="admin_yx@x.ru", name="A", role="org_admin", status="active", is_superuser=True)
    db.add(u)
    db.commit()
    return u


def _estimator(db):
    u = User(email="est_yx@x.ru", name="E", role="estimator", status="active")
    db.add(u)
    db.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_yandex_settings_initial_state(client, db_session):
    a = _admin(db_session)
    r = client.get("/api/settings/yandex", headers=_hdr(a))
    assert r.status_code == 200
    data = r.json()
    assert data == {"client_id": "", "has_secret": False}


def test_yandex_settings_put_sets_values(client, db_session):
    a = _admin(db_session)
    r = client.put(
        "/api/settings/yandex",
        headers=_hdr(a),
        json={"client_id": "my-client-id", "secret": "my-secret"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["client_id"] == "my-client-id"
    assert data["has_secret"] is True


def test_yandex_settings_get_returns_client_id_not_secret(client, db_session):
    a = _admin(db_session)
    client.put(
        "/api/settings/yandex",
        headers=_hdr(a),
        json={"client_id": "visible-id", "secret": "super-secret"},
    )
    r = client.get("/api/settings/yandex", headers=_hdr(a))
    data = r.json()
    # client_id виден
    assert data["client_id"] == "visible-id"
    # секрет НИКОГДА не возвращается, только флаг
    assert "secret" not in data
    assert data["has_secret"] is True


def test_yandex_settings_empty_put_leaves_values_unchanged(client, db_session):
    a = _admin(db_session)
    client.put(
        "/api/settings/yandex",
        headers=_hdr(a),
        json={"client_id": "orig-id", "secret": "orig-secret"},
    )
    # PUT с пустыми полями — ничего не меняет
    client.put(
        "/api/settings/yandex",
        headers=_hdr(a),
        json={"client_id": "", "secret": ""},
    )
    r = client.get("/api/settings/yandex", headers=_hdr(a))
    data = r.json()
    assert data["client_id"] == "orig-id"
    assert data["has_secret"] is True
    # Проверяем реальное значение через service
    assert settings_service.get_secret(db_session, YANDEX_CLIENT_SECRET) == "orig-secret"


def test_yandex_settings_non_admin_403(client, db_session):
    e = _estimator(db_session)
    assert client.get("/api/settings/yandex", headers=_hdr(e)).status_code == 403
    assert (
        client.put(
            "/api/settings/yandex",
            headers=_hdr(e),
            json={"client_id": "x", "secret": "y"},
        ).status_code
        == 403
    )


def test_yandex_service_roundtrip(db_session):
    """Базовая проверка что service корректно хранит/возвращает значения."""
    assert settings_service.has_secret(db_session, YANDEX_CLIENT_ID) is False
    assert settings_service.has_secret(db_session, YANDEX_CLIENT_SECRET) is False
    settings_service.set_secret(db_session, YANDEX_CLIENT_ID, "client-123")
    settings_service.set_secret(db_session, YANDEX_CLIENT_SECRET, "secret-abc")
    assert settings_service.get_secret(db_session, YANDEX_CLIENT_ID) == "client-123"
    assert settings_service.get_secret(db_session, YANDEX_CLIENT_SECRET) == "secret-abc"
    assert settings_service.has_secret(db_session, YANDEX_CLIENT_ID) is True
    assert settings_service.has_secret(db_session, YANDEX_CLIENT_SECRET) is True
