from app.auth.models import User
from app.core.security import create_access_token
from app.settings import service as settings_service


def _admin(db):
    u = User(email="a@x.ru", name="A", role="org_admin", status="active")
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_secret_roundtrip_and_has(db_session):
    assert settings_service.has_secret(db_session, "dadata_token") is False
    settings_service.set_secret(db_session, "dadata_token", "tok-123")
    assert settings_service.has_secret(db_session, "dadata_token") is True
    assert settings_service.get_secret(db_session, "dadata_token") == "tok-123"


def test_dadata_settings_endpoints(client, db_session):
    a = _admin(db_session)
    assert client.get("/api/settings/dadata", headers=_hdr(a)).json() == {
        "has_token": False, "has_secret": False}
    r = client.put("/api/settings/dadata", headers=_hdr(a), json={"token": "T", "secret": "S"})
    assert r.status_code == 200
    assert client.get("/api/settings/dadata", headers=_hdr(a)).json() == {
        "has_token": True, "has_secret": True}


def test_dadata_put_blank_keeps_existing(client, db_session):
    a = _admin(db_session)
    client.put("/api/settings/dadata", headers=_hdr(a), json={"token": "T", "secret": "S"})
    client.put("/api/settings/dadata", headers=_hdr(a), json={"token": "", "secret": ""})
    assert client.get("/api/settings/dadata", headers=_hdr(a)).json() == {
        "has_token": True, "has_secret": True}


def test_dadata_settings_admin_only(client, db_session):
    e = User(email="e@x.ru", name="E", role="estimator", status="active")
    db_session.add(e); db_session.commit()
    assert client.get("/api/settings/dadata", headers=_hdr(e)).status_code == 403
