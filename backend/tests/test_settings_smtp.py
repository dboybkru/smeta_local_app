"""
Тесты для GET/PUT /api/settings/smtp.
Зеркалят паттерн test_settings_yandex.py.
"""

from app.auth.models import User
from app.core.security import create_access_token


def _superuser(db):
    u = User(email="su_smtp@x.ru", name="SU", role="org_admin", status="active", is_superuser=True)
    db.add(u)
    db.commit()
    return u


def _org_admin(db):
    u = User(email="oa_smtp@x.ru", name="OA", role="org_admin", status="active", is_superuser=False)
    db.add(u)
    db.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_smtp_put_get_roundtrip(client, db_session):
    su = _superuser(db_session)
    r = client.put(
        "/api/settings/smtp",
        json={
            "host": "smtp.test",
            "port": "587",
            "user": "u@x.ru",
            "password": "secret",
            "from_addr": "from@x.ru",
            "tls": "true",
        },
        headers=_hdr(su),
    )
    assert r.status_code == 200
    g = client.get("/api/settings/smtp", headers=_hdr(su)).json()
    assert g["host"] == "smtp.test"
    assert g["has_password"] is True
    # пароль не возвращается в открытом виде
    assert "password" not in g or g.get("password") in (None, "")


def test_smtp_requires_superuser(client, db_session):
    oa = _org_admin(db_session)
    assert client.get("/api/settings/smtp", headers=_hdr(oa)).status_code == 403
    assert (
        client.put(
            "/api/settings/smtp",
            json={
                "host": "smtp.test",
                "port": "587",
                "user": "u@x.ru",
                "password": "secret",
                "from_addr": "from@x.ru",
                "tls": "true",
            },
            headers=_hdr(oa),
        ).status_code
        == 403
    )


def test_smtp_empty_put_leaves_values_unchanged(client, db_session):
    su = _superuser(db_session)
    client.put(
        "/api/settings/smtp",
        json={
            "host": "smtp.orig",
            "port": "465",
            "user": "orig@x.ru",
            "password": "origpw",
            "from_addr": "orig@x.ru",
            "tls": "false",
        },
        headers=_hdr(su),
    )
    # PUT с пустыми полями — ничего не меняет
    client.put(
        "/api/settings/smtp",
        json={"host": "", "port": "", "user": "", "password": "", "from_addr": "", "tls": ""},
        headers=_hdr(su),
    )
    g = client.get("/api/settings/smtp", headers=_hdr(su)).json()
    assert g["host"] == "smtp.orig"
    assert g["has_password"] is True


def test_smtp_initial_state(client, db_session):
    su = _superuser(db_session)
    r = client.get("/api/settings/smtp", headers=_hdr(su))
    assert r.status_code == 200
    data = r.json()
    assert data["host"] in (None, "")
    assert data["has_password"] is False
