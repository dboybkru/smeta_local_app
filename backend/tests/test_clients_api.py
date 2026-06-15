from sqlalchemy import select

from app.auth.models import User
from app.core.security import create_access_token
from app.orgs.models import Organization


def _get_org(db_session):
    org = db_session.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db_session.add(org)
        db_session.commit()
    return org


def _auth(db_session, role="estimator"):
    org = _get_org(db_session)
    u = User(email=f"{role}@x.ru", name="U", role=role, status="active", org_id=org.id)
    db_session.add(u)
    db_session.commit()
    # create_access_token принимает user_id: int, role: str
    return {"Authorization": f"Bearer {create_access_token(u.id, role)}"}


def test_create_and_list_clients(client, db_session):
    h = _auth(db_session)
    r = client.post("/api/clients", json={"name": "ООО Ромашка"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "ООО Ромашка"

    r = client.get("/api/clients", headers=h)
    assert r.status_code == 200
    assert [c["name"] for c in r.json()] == ["ООО Ромашка"]


def test_clients_require_auth(client):
    assert client.get("/api/clients").status_code == 401


def test_viewer_cannot_create_client(client, db_session):
    h = _auth(db_session, role="viewer")
    r = client.post("/api/clients", json={"name": "ООО Тест"}, headers=h)
    assert r.status_code == 403, r.text
