from app.auth.models import User
from app.core.security import create_access_token


def _user(db, role="org_admin", su=False, status="active"):
    u = User(email=f"{role}{su}@x.ru", name="U", role=role, status=status, is_superuser=su)
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_superuser_creates_and_lists_orgs(client, db_session):
    su = _user(db_session, su=True)
    r = client.post("/api/orgs", json={"name": "Фирма А"}, headers=_hdr(su))
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Фирма А"
    lst = client.get("/api/orgs", headers=_hdr(su)).json()
    assert any(o["name"] == "Фирма А" for o in lst)


def test_duplicate_org_name_409(client, db_session):
    su = _user(db_session, su=True)
    client.post("/api/orgs", json={"name": "Дубль"}, headers=_hdr(su))
    assert client.post("/api/orgs", json={"name": "Дубль"}, headers=_hdr(su)).status_code == 409


def test_non_superuser_cannot_manage_orgs(client, db_session):
    admin = _user(db_session, role="org_admin", su=False)
    assert client.get("/api/orgs", headers=_hdr(admin)).status_code == 403
    assert client.post("/api/orgs", json={"name": "X"}, headers=_hdr(admin)).status_code == 403
