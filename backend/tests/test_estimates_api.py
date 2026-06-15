from sqlalchemy import select

from app.auth.models import User
from app.core.security import create_access_token
from app.orgs.models import Organization


def _get_org(db_session):
    """Return or create the single test org for this session."""
    org = db_session.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db_session.add(org)
        db_session.commit()
    return org


def _user(db_session, role="estimator", email=None):
    org = _get_org(db_session)
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active", org_id=org.id)
    db_session.add(u)
    db_session.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_create_estimate_makes_base_branch(client, db_session):
    u = _user(db_session)
    r = client.post("/api/estimates", json={"object_name": "Объект"}, headers=_hdr(u))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["object_name"] == "Объект"
    assert len(body["branches"]) == 1
    assert body["branches"][0]["name"] == "Базовая"


def test_owner_sees_only_own_estimates(client, db_session):
    a = _user(db_session, email="a@x.ru")
    b = _user(db_session, email="b@x.ru")
    client.post("/api/estimates", json={"object_name": "A"}, headers=_hdr(a))
    r = client.get("/api/estimates", headers=_hdr(b))
    assert r.status_code == 200
    assert r.json() == []


def test_admin_sees_all_estimates(client, db_session):
    a = _user(db_session, email="a@x.ru")
    admin = _user(db_session, role="org_admin", email="adm@x.ru")
    client.post("/api/estimates", json={"object_name": "A"}, headers=_hdr(a))
    r = client.get("/api/estimates", headers=_hdr(admin))
    assert len(r.json()) == 1


def test_get_foreign_estimate_404(client, db_session):
    a = _user(db_session, email="a@x.ru")
    b = _user(db_session, email="b@x.ru")
    rid = client.post("/api/estimates", json={"object_name": "A"}, headers=_hdr(a)).json()["id"]
    assert client.get(f"/api/estimates/{rid}", headers=_hdr(b)).status_code == 404


def test_patch_and_delete_estimate(client, db_session):
    u = _user(db_session)
    rid = client.post("/api/estimates", json={"object_name": "A"}, headers=_hdr(u)).json()["id"]
    r = client.patch(
        f"/api/estimates/{rid}",
        json={"vat_enabled": True, "vat_rate": "10"},
        headers=_hdr(u),
    )
    assert r.json()["vat_enabled"] is True
    assert r.json()["vat_rate"] == "10.00"
    assert client.delete(f"/api/estimates/{rid}", headers=_hdr(u)).status_code == 204
    assert client.get(f"/api/estimates/{rid}", headers=_hdr(u)).status_code == 404
