from app.auth.models import User
from app.core.security import create_access_token
from app.estimates.models import Estimate
from tests.orghelpers import get_or_create_org as _get_org


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


def test_create_list_revoke(client, db_session):
    u = _user(db_session)
    est = _estimate(db_session, u)
    r = client.post(
        f"/api/estimates/{est.id}/public-links",
        json={"level": "cover", "watermark_enabled": True, "watermark_text": "ОБРАЗЕЦ"},
        headers=_hdr(u),
    )
    assert r.status_code == 201, r.text
    link = r.json()
    assert link["level"] == "cover"
    assert link["token"]
    assert link["revoked"] is False

    lst = client.get(f"/api/estimates/{est.id}/public-links", headers=_hdr(u))
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    d = client.delete(f"/api/public-links/{link['id']}", headers=_hdr(u))
    assert d.status_code == 204
    lst2 = client.get(f"/api/estimates/{est.id}/public-links", headers=_hdr(u))
    assert lst2.json()[0]["revoked"] is True


def test_create_foreign_404(client, db_session):
    a = _user(db_session, email="a@x.ru")
    b = _user(db_session, email="b@x.ru")
    est = _estimate(db_session, a)
    r = client.post(f"/api/estimates/{est.id}/public-links", json={}, headers=_hdr(b))
    assert r.status_code == 404


# --- resolve_token (service-level, used by public router) ---
import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app.publiclinks import service as pl_service  # noqa: E402
from app.publiclinks.models import PublicLink  # noqa: E402


def _link(db_session, **kwargs):
    u = _user(db_session, email="lnk@x.ru")
    est = _estimate(db_session, u)
    link = PublicLink(estimate_id=est.id, token=kwargs.pop("token", "tk"), **kwargs)
    db_session.add(link)
    db_session.commit()
    return link


def test_resolve_token_ok(db_session):
    link = _link(db_session, token="tk-ok")
    assert pl_service.resolve_token(db_session, "tk-ok").id == link.id


def test_resolve_token_revoked_404(db_session):
    _link(db_session, token="tk-rev", revoked=True)
    with pytest.raises(HTTPException) as exc:
        pl_service.resolve_token(db_session, "tk-rev")
    assert exc.value.status_code == 404


def test_resolve_token_missing_404(db_session):
    with pytest.raises(HTTPException) as exc:
        pl_service.resolve_token(db_session, "nope")
    assert exc.value.status_code == 404


def test_resolve_token_expired_410(db_session):
    from datetime import UTC, datetime, timedelta

    _link(db_session, token="tk-exp", expires_at=datetime.now(UTC) - timedelta(days=1))
    with pytest.raises(HTTPException) as exc:
        pl_service.resolve_token(db_session, "tk-exp")
    assert exc.value.status_code == 410
