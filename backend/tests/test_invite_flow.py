import sqlalchemy
from datetime import UTC, datetime, timedelta

from app.auth.models import User
from app.core.security import create_access_token
from app.orgs.models import Organization
import app.email.sender as email_sender


def test_user_has_invite_token_columns(db_session):
    o = Organization(name="IT"); db_session.add(o); db_session.commit()
    u = User(email="i@x.ru", name="", role="estimator", status="invited", org_id=o.id,
             invite_token="tok123", invite_expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    assert u.invite_token == "tok123" and u.invite_expires_at is not None


def _su(db):
    o = Organization(name="INV"); db.add(o); db.commit()
    su = User(email="suinv@x.ru", name="S", role="org_admin", status="active",
              is_superuser=True, org_id=o.id)
    db.add(su); db.commit(); return su, o


def _h(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_invite_generates_token_and_sends(client, db_session, monkeypatch):
    su, o = _su(db_session)
    calls = {}
    monkeypatch.setattr(email_sender, "send_invite_email",
                        lambda db, to, org_name, link, **k: calls.update(to=to, link=link))
    r = client.post(f"/api/orgs/{o.id}/users", json={"email": "new@x.ru", "role": "estimator"},
                    headers=_h(su))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email_sent"] is True and "/invite/" in body["invite_link"]
    u = db_session.scalars(sqlalchemy.select(User).where(User.email == "new@x.ru")).one()
    assert u.invite_token and u.invite_expires_at and calls["to"] == "new@x.ru"


def test_invite_graceful_when_email_unconfigured(client, db_session, monkeypatch):
    su, o = _su(db_session)
    def _raise(*a, **k): raise email_sender.EmailNotConfigured()
    monkeypatch.setattr(email_sender, "send_invite_email", _raise)
    r = client.post(f"/api/orgs/{o.id}/users", json={"email": "n2@x.ru", "role": "viewer"},
                    headers=_h(su))
    assert r.status_code == 201 and r.json()["email_sent"] is False
    assert "/invite/" in r.json()["invite_link"]  # ссылку показываем админу


def test_resend_invite(client, db_session, monkeypatch):
    su, o = _su(db_session)
    calls = {}
    monkeypatch.setattr(email_sender, "send_invite_email",
                        lambda db, to, org_name, link, **k: calls.update(to=to, link=link))
    # создаём инвайт
    r = client.post(f"/api/orgs/{o.id}/users", json={"email": "resend@x.ru", "role": "estimator"},
                    headers=_h(su))
    assert r.status_code == 201

    # получаем uid
    u = db_session.scalars(sqlalchemy.select(User).where(User.email == "resend@x.ru")).one()
    old_token = u.invite_token

    calls.clear()
    # resend
    r2 = client.post(f"/api/orgs/{o.id}/users/{u.id}/resend-invite", headers=_h(su))
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["email_sent"] is True and "/invite/" in body2["invite_link"]
    # токен должен обновиться
    db_session.refresh(u)
    assert u.invite_token != old_token
    assert calls["to"] == "resend@x.ru"


def test_resend_invite_404_for_non_invited(client, db_session, monkeypatch):
    su, o = _su(db_session)
    monkeypatch.setattr(email_sender, "send_invite_email", lambda *a, **k: None)
    # active user
    active = User(email="active@x.ru", name="A", role="estimator", status="active", org_id=o.id)
    db_session.add(active); db_session.commit()
    r = client.post(f"/api/orgs/{o.id}/users/{active.id}/resend-invite", headers=_h(su))
    assert r.status_code == 404


def test_invite_info_and_accept(client, db_session, monkeypatch):
    su, o = _su(db_session)
    monkeypatch.setattr(email_sender, "send_invite_email", lambda *a, **k: None)
    inv = client.post(f"/api/orgs/{o.id}/users", json={"email": "ac@x.ru", "role": "estimator"},
                      headers=_h(su)).json()
    token = inv["invite_link"].rsplit("/invite/", 1)[1]
    info = client.get(f"/api/auth/invite/{token}")
    assert info.status_code == 200 and info.json()["email"] == "ac@x.ru"
    acc = client.post(f"/api/auth/invite/{token}/accept",
                      json={"name": "Acme", "password": "Pass12345"})
    assert acc.status_code == 200 and acc.json()["status"] == "active"
    u = db_session.scalars(sqlalchemy.select(User).where(User.email == "ac@x.ru")).one()
    assert u.status == "active" and u.invite_token is None and u.password_hash
    # повторный accept → 404 (токен погашен)
    assert client.post(f"/api/auth/invite/{token}/accept",
                       json={"name": "X", "password": "Pass12345"}).status_code == 404


def test_register_invite_only_when_users_exist(client, db_session):
    _su(db_session)  # юзеры уже есть
    r = client.post("/api/auth/register",
                    json={"email": "open@x.ru", "password": "Pass12345", "name": "O"})
    assert r.status_code == 403
