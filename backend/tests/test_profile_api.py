from app.auth.models import User
from app.core.security import create_access_token
from app.orgs.models import Organization


def _org(db_session, name="TestOrg"):
    o = Organization(name=name)
    db_session.add(o)
    db_session.commit()
    return o


def _user(db_session, role="org_admin", email=None, org=None):
    if org is None:
        org = _org(db_session)
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active", org_id=org.id)
    db_session.add(u)
    db_session.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_get_profile_returns_empty_when_absent(client, db_session):
    u = _user(db_session)
    r = client.get("/api/profile", headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["org_name"] == ""
    assert r.json()["contacts"] == {}


def test_put_profile_upserts(client, db_session):
    u = _user(db_session)
    payload = {
        "org_name": "ООО Ромашка",
        "inn": "7701234567",
        "contacts": {"phone": "+7 900 000-00-00", "email": "a@b.ru"},
        "utp": ["Гарантия 5 лет", "Свои бригады"],
        "cases": ["ЖК Заря — 1200 м²"],
        "guarantee": "5 лет на работы",
        "bank_requisites": "р/с 4070...",
    }
    r = client.put("/api/profile", json=payload, headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["org_name"] == "ООО Ромашка"
    assert r.json()["utp"] == ["Гарантия 5 лет", "Свои бригады"]
    r2 = client.put("/api/profile", json={**payload, "org_name": "ООО Лютик"}, headers=_hdr(u))
    assert r2.status_code == 200
    assert r2.json()["org_name"] == "ООО Лютик"
    r3 = client.get("/api/profile", headers=_hdr(u))
    assert r3.json()["org_name"] == "ООО Лютик"


def test_profile_requires_auth(client):
    assert client.get("/api/profile").status_code == 401
