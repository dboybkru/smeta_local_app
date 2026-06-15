from app.auth.models import User
from app.core.security import create_access_token
from app.estimates import models as em
from app.orgs.models import Organization


def _org_user(db, name):
    o = Organization(name=name); db.add(o); db.commit()
    u = User(email=f"a{name}@x.ru", name="A", role="org_admin", status="active", org_id=o.id)
    db.add(u); db.commit(); return o, u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_estimate_not_visible_across_orgs(client, db_session):
    oa, ua = _org_user(db_session, "A"); ob, ub = _org_user(db_session, "B")
    est = em.Estimate(owner_id=ua.id, org_id=oa.id, object_name="Секрет A")
    db_session.add(est); db_session.commit()
    assert client.get(f"/api/estimates/{est.id}", headers=_hdr(ub)).status_code == 404
    lst = client.get("/api/estimates", headers=_hdr(ub)).json()
    assert all(e["id"] != est.id for e in (lst if isinstance(lst, list) else lst.get("items", [])))
    assert client.get(f"/api/estimates/{est.id}", headers=_hdr(ua)).status_code == 200


def test_client_isolated_across_orgs(client, db_session):
    oa, ua = _org_user(db_session, "CA"); ob, ub = _org_user(db_session, "CB")
    db_session.add(em.Client(name="Клиент A", org_id=oa.id)); db_session.commit()
    lst = client.get("/api/clients", headers=_hdr(ub)).json()
    assert all(c["name"] != "Клиент A" for c in lst)
