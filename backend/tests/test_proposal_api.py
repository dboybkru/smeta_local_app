from sqlalchemy import select

from app.ai import service as ai_service
from app.ai.errors import AINotConfigured
from app.auth.models import User
from app.core.security import create_access_token
from app.estimates.models import Estimate
from app.orgs.models import Organization


def _get_org(db_session):
    org = db_session.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db_session.add(org)
        db_session.commit()
    return org


def _user(db_session, role="estimator", email=None):
    org = _get_org(db_session)
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active", org_id=org.id)
    db_session.add(u); db_session.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _estimate(db_session, owner):
    org = _get_org(db_session)
    est = Estimate(owner_id=owner.id, org_id=org.id, object_name="Объект")
    db_session.add(est); db_session.commit(); db_session.refresh(est)
    return est


def test_generate_persists_blocks(client, db_session, monkeypatch):
    u = _user(db_session)
    est = _estimate(db_session, u)
    fake = {"title": "T", "subtitle": "S", "pain": "P", "solution": "Sol",
            "advantages": ["A"], "terms": "Tm", "cta": "C"}
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: fake)
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "T"
    db_session.refresh(est)
    assert est.proposal["title"] == "T"


def test_generate_503_without_config(client, db_session, monkeypatch):
    u = _user(db_session)
    est = _estimate(db_session, u)
    def boom(*a, **k):
        raise AINotConfigured("нет модели")
    monkeypatch.setattr(ai_service, "call_llm", boom)
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(u))
    assert r.status_code == 503


def test_patch_partial_and_clear(client, db_session):
    u = _user(db_session)
    est = _estimate(db_session, u)
    est.proposal = {"title": "Old", "cta": "Звоните"}
    db_session.commit()
    r = client.patch(f"/api/estimates/{est.id}/proposal", json={"title": "New"}, headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "New"
    assert r.json()["cta"] == "Звоните"


def test_generate_foreign_estimate_404(client, db_session, monkeypatch):
    a = _user(db_session, email="a@x.ru")
    b = _user(db_session, email="b@x.ru")
    est = _estimate(db_session, a)
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {
        "title": "", "subtitle": "", "pain": "", "solution": "",
        "advantages": [], "terms": "", "cta": ""})
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(b))
    assert r.status_code == 404
