from app.auth.models import User
from app.core.security import create_access_token


def _u(db, role="estimator"):
    u = User(email=f"{role}@x.ru", name="U", role=role, status="active")
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_create_client_with_requisites(client, db_session):
    u = _u(db_session)
    r = client.post("/api/clients", headers=_hdr(u), json={
        "name": "ООО Ромашка", "inn": "7707083893", "kpp": "773601001",
        "phone": "+79990001122", "email": "a@b.ru"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["inn"] == "7707083893" and body["email"] == "a@b.ru"


def test_patch_client(client, db_session):
    u = _u(db_session)
    cid = client.post("/api/clients", headers=_hdr(u), json={"name": "К"}).json()["id"]
    r = client.patch(f"/api/clients/{cid}", headers=_hdr(u), json={"inn": "123", "address": "Москва"})
    assert r.status_code == 200, r.text
    assert r.json()["inn"] == "123" and r.json()["address"] == "Москва"


def test_get_client(client, db_session):
    u = _u(db_session)
    cid = client.post("/api/clients", headers=_hdr(u), json={"name": "К", "inn": "9"}).json()["id"]
    assert client.get(f"/api/clients/{cid}", headers=_hdr(u)).json()["inn"] == "9"


def test_viewer_cannot_create_client(client, db_session):
    v = _u(db_session, role="viewer")
    assert client.post("/api/clients", headers=_hdr(v), json={"name": "К"}).status_code == 403
