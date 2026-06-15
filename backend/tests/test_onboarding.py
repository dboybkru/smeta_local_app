import sqlalchemy as sa

from app.auth.models import User
from app.core.security import create_access_token
from app.orgs.models import Organization


def _su(db):
    o = Organization(name="O1"); db.add(o); db.commit()
    su = User(email="su@x.ru", name="S", role="org_admin", status="active",
              is_superuser=True, org_id=o.id)
    db.add(su); db.commit(); return su, o


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_invite_creates_invited_user(client, db_session):
    su, o = _su(db_session)
    r = client.post(f"/api/orgs/{o.id}/users", json={"email": "new@x.ru", "role": "estimator"},
                    headers=_hdr(su))
    assert r.status_code == 201, r.text
    u = db_session.scalars(sa.select(User).where(User.email == "new@x.ru")).one()
    assert u.status == "invited" and u.org_id == o.id and u.role == "estimator"


def test_register_claims_invited(client, db_session):
    su, o = _su(db_session)
    client.post(f"/api/orgs/{o.id}/users", json={"email": "claim@x.ru", "role": "estimator"},
                headers=_hdr(su))
    r = client.post("/api/auth/register", json={"email": "claim@x.ru", "password": "Pass12345",
                                                "name": "Claimed"})
    assert r.status_code in (200, 201), r.text
    u = db_session.scalars(sa.select(User).where(User.email == "claim@x.ru")).one()
    assert u.status == "active" and u.org_id == o.id and u.password_hash


def test_self_register_without_invite_is_pending_orgless(client, db_session):
    _su(db_session)  # система уже не пустая
    r = client.post("/api/auth/register", json={"email": "self@x.ru", "password": "Pass12345",
                                                "name": "Self"})
    assert r.status_code in (200, 201)
    u = db_session.scalars(sa.select(User).where(User.email == "self@x.ru")).one()
    assert u.status == "pending" and u.org_id is None


def test_yandex_claim_invited_user(db_session):
    """Яндекс-вход по email должен «забирать» приглашённого пользователя."""
    from app.auth.service import get_or_create_yandex_user

    o = Organization(name="OrgY")
    db_session.add(o)
    db_session.commit()

    invited = User(
        email="yaclaim@example.ru",
        role="viewer",
        status="invited",
        org_id=o.id,
        name="",
    )
    db_session.add(invited)
    db_session.commit()

    info = {"id": "yx-claim-999", "default_email": "yaclaim@example.ru", "real_name": "Яша"}
    user = get_or_create_yandex_user(db_session, info)

    assert user.status == "active"
    assert user.yandex_id == "yx-claim-999"
    assert user.org_id == o.id
    assert user.role == "viewer"
