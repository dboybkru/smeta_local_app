from app.auth.models import User
from app.core.security import create_access_token
from app.orgs.models import Organization


def _org_admin(db, name):
    o = Organization(name=name); db.add(o); db.commit()
    u = User(email=f"p{name}@x.ru", name="A", role="org_admin", status="active", org_id=o.id)
    db.add(u); db.commit(); return o, u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_profile_is_per_org(client, db_session):
    oa, ua = _org_admin(db_session, "PRA"); ob, ub = _org_admin(db_session, "PRB")
    client.put("/api/profile", json={"org_name": "Фирма А"}, headers=_hdr(ua))
    assert client.get("/api/profile", headers=_hdr(ub)).json().get("org_name") != "Фирма А"
    assert client.get("/api/profile", headers=_hdr(ua)).json().get("org_name") == "Фирма А"


def test_ai_config_requires_superuser(client, db_session):
    oa, ua = _org_admin(db_session, "AIA")  # org_admin, NOT superuser
    assert client.get("/api/ai/providers", headers=_hdr(ua)).status_code == 403
