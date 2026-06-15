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


def test_rename_org(client, db_session):
    su = _user(db_session, su=True)
    hdr = _hdr(su)

    # create org and rename it
    r = client.post("/api/orgs", json={"name": "Старое имя"}, headers=hdr)
    assert r.status_code == 201
    org_id = r.json()["id"]

    r = client.patch(f"/api/orgs/{org_id}", json={"name": "Новое имя"}, headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Новое имя"
    assert data["id"] == org_id
    assert "user_count" in data


def test_rename_org_duplicate_name_409(client, db_session):
    su = _user(db_session, su=True)
    hdr = _hdr(su)

    r1 = client.post("/api/orgs", json={"name": "Орг Один"}, headers=hdr)
    assert r1.status_code == 201
    r2 = client.post("/api/orgs", json={"name": "Орг Два"}, headers=hdr)
    assert r2.status_code == 201
    org2_id = r2.json()["id"]

    # try to rename Орг Два to the name already taken by Орг Один
    r = client.patch(f"/api/orgs/{org2_id}", json={"name": "Орг Один"}, headers=hdr)
    assert r.status_code == 409


def test_rename_nonexistent_org_404(client, db_session):
    su = _user(db_session, su=True)
    r = client.patch("/api/orgs/99999", json={"name": "Любое"}, headers=_hdr(su))
    assert r.status_code == 404
