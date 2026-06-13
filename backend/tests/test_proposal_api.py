from app.auth.models import User
from app.core.security import create_access_token
from app.estimates.models import Estimate
from app.proposals import service


def _user(db_session, role="estimator", email=None):
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active")
    db_session.add(u)
    db_session.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _estimate(db_session, owner):
    est = Estimate(owner_id=owner.id, object_name="Объект")
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


def test_generate_persists_blocks(client, db_session, monkeypatch):
    u = _user(db_session)
    est = _estimate(db_session, u)
    monkeypatch.setattr(service.settings, "anthropic_api_key", "sk-test")
    fake = {"title": "T", "subtitle": "S", "pain": "P", "solution": "Sol",
            "advantages": ["A"], "terms": "Tm", "cta": "C"}
    monkeypatch.setattr(service, "_call_claude", lambda prompt: fake)
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "T"
    db_session.refresh(est)
    assert est.proposal["title"] == "T"


def test_generate_503_without_key(client, db_session, monkeypatch):
    u = _user(db_session)
    est = _estimate(db_session, u)
    monkeypatch.setattr(service.settings, "anthropic_api_key", "")
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(u))
    assert r.status_code == 503


def test_patch_partial_and_clear(client, db_session):
    u = _user(db_session)
    est = _estimate(db_session, u)
    est.proposal = {"title": "Old", "cta": "Звоните"}
    db_session.commit()
    r = client.patch(
        f"/api/estimates/{est.id}/proposal", json={"title": "New"}, headers=_hdr(u)
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "New"
    assert r.json()["cta"] == "Звоните"  # не затёрто


def test_generate_foreign_estimate_404(client, db_session, monkeypatch):
    a = _user(db_session, email="a@x.ru")
    b = _user(db_session, email="b@x.ru")
    est = _estimate(db_session, a)
    monkeypatch.setattr(service.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(service, "_call_claude", lambda p: {
        "title": "", "subtitle": "", "pain": "", "solution": "",
        "advantages": [], "terms": "", "cta": ""})
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(b))
    assert r.status_code == 404
