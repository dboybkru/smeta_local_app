from app.auth.models import User
from app.core.security import create_access_token


def _user(db_session, role="estimator", email=None):
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active")
    db_session.add(u)
    db_session.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _estimate(client, u):
    return client.post("/api/estimates", json={"object_name": "O"}, headers=_hdr(u)).json()


def test_add_section_to_base_branch(client, db_session):
    u = _user(db_session)
    est = _estimate(client, u)
    r = client.post(
        f"/api/estimates/{est['id']}/sections",
        json={"name": "Оборудование"},
        headers=_hdr(u),
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Оборудование"
    assert r.json()["markup_percent"] == "0.00"


def test_patch_and_delete_section(client, db_session):
    u = _user(db_session)
    est = _estimate(client, u)
    sid = client.post(
        f"/api/estimates/{est['id']}/sections",
        json={"name": "S"},
        headers=_hdr(u),
    ).json()["id"]
    r = client.patch(f"/api/sections/{sid}", json={"markup_percent": "15"}, headers=_hdr(u))
    assert r.json()["markup_percent"] == "15.00"
    assert client.delete(f"/api/sections/{sid}", headers=_hdr(u)).status_code == 204


def test_cannot_add_section_to_foreign_estimate(client, db_session):
    a = _user(db_session, email="a@x.ru")
    b = _user(db_session, email="b@x.ru")
    est = _estimate(client, a)
    r = client.post(
        f"/api/estimates/{est['id']}/sections",
        json={"name": "S"},
        headers=_hdr(b),
    )
    assert r.status_code == 404
