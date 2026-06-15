from sqlalchemy import select

from app.auth.models import User
from app.core.security import create_access_token
from app.estimates.models import Estimate
from app.export import router as export_router
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
    db_session.add(u)
    db_session.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _estimate(db_session, owner):
    org = _get_org(db_session)
    est = Estimate(owner_id=owner.id, org_id=org.id, object_name="Объект")
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


def test_export_xlsx_ok(client, db_session):
    u = _user(db_session)
    est = _estimate(db_session, u)
    r = client.get(f"/api/estimates/{est.id}/export.xlsx?level=estimate", headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert "spreadsheet" in r.headers["content-type"]
    assert r.content[:2] == b"PK"  # xlsx = zip


def test_export_pdf_ok(client, db_session, monkeypatch):
    u = _user(db_session)
    est = _estimate(db_session, u)
    monkeypatch.setattr(export_router.render, "html_to_pdf", lambda html: b"%PDF-1.7 mock")
    r = client.get(f"/api/estimates/{est.id}/export.pdf?level=full", headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_export_foreign_404(client, db_session):
    a = _user(db_session, email="a@x.ru")
    b = _user(db_session, email="b@x.ru")
    est = _estimate(db_session, a)
    assert client.get(f"/api/estimates/{est.id}/export.xlsx", headers=_hdr(b)).status_code == 404
