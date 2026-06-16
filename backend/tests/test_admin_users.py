"""Tests for /api/admin/users — доступ только для superuser.

Первый зарегистрированный пользователь автоматически получает is_superuser=True
(см. app.auth.service.register_user). Все тесты, которым нужен суперпользователь,
регистрируют его первым.
После Task 5 открытая регистрация закрыта (invite-only), поэтому второй и последующий
пользователи создаются через БД напрямую.
"""

from app.auth.models import User
from app.core.security import create_access_token, hash_password


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_user(client, email):
    """Bootstrap first user via register endpoint (only allowed when DB is empty)."""
    resp = client.post(
        "/api/auth/register", json={"email": email, "password": "secret123", "name": "Т"}
    )
    assert resp.status_code == 201
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
    user_data = resp.json()
    # Очищаем cookie-jar чтобы Bearer-заголовки не перекрывались cookie следующего login
    client.cookies.clear()
    return {
        "access_token": create_access_token(user_data["id"], user_data["role"]),
        "id": user_data["id"],
        "role": user_data["role"],
    }


def make_user_db(db_session, email, status="pending", role="estimator"):
    """Create additional users directly in DB (register endpoint is invite-only after bootstrap)."""
    u = User(
        email=email,
        password_hash=hash_password("secret123"),
        name="Т",
        role=role,
        status=status,
    )
    db_session.add(u)
    db_session.commit()
    return {
        "access_token": create_access_token(u.id, u.role),
        "id": u.id,
        "role": u.role,
    }


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _org_admin_hdr(db_session):
    """Создаёт org_admin БЕЗ is_superuser напрямую в БД и возвращает заголовок."""
    u = User(
        email="orgadmin@test.ru",
        password_hash=None,
        name="OrgAdmin",
        role="org_admin",
        status="active",
        is_superuser=False,
    )
    db_session.add(u)
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


# ---------------------------------------------------------------------------
# superuser happy-path tests
# ---------------------------------------------------------------------------

def test_superuser_lists_users(client, db_session):
    """Первый зарегистрированный = superuser; может видеть всех пользователей."""
    superuser = make_user(client, "superuser@test.ru")
    make_user_db(db_session, "second@test.ru")
    resp = client.get("/api/admin/users", headers=auth(superuser))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_non_admin_cannot_list_users(client, db_session):
    make_user(client, "superuser@test.ru")
    second = make_user_db(db_session, "second@test.ru")
    resp = client.get("/api/admin/users", headers=auth(second))
    assert resp.status_code == 403


def test_superuser_approves_pending_user(client, db_session):
    superuser = make_user(client, "superuser@test.ru")
    make_user_db(db_session, "second@test.ru")
    users = client.get("/api/admin/users", headers=auth(superuser)).json()
    pending_id = next(u["id"] for u in users if u["status"] == "pending")
    resp = client.post(
        f"/api/admin/users/{pending_id}/status",
        json={"status": "active"},
        headers=auth(superuser),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_status_change_unknown_user_404(client):
    superuser = make_user(client, "superuser@test.ru")
    resp = client.post(
        "/api/admin/users/999/status", json={"status": "active"}, headers=auth(superuser)
    )
    assert resp.status_code == 404


def test_invalid_status_rejected(client):
    superuser = make_user(client, "superuser@test.ru")
    resp = client.post(
        "/api/admin/users/1/status", json={"status": "superuser"}, headers=auth(superuser)
    )
    assert resp.status_code == 422


def test_superuser_cannot_block_self(client):
    superuser = make_user(client, "superuser@test.ru")
    me = client.get("/api/auth/me", headers=auth(superuser)).json()
    resp = client.post(
        f"/api/admin/users/{me['id']}/status", json={"status": "blocked"}, headers=auth(superuser)
    )
    assert resp.status_code == 400


def test_superuser_blocks_other_user(client, db_session):
    superuser = make_user(client, "superuser@test.ru")
    make_user_db(db_session, "second@test.ru")
    users = client.get("/api/admin/users", headers=auth(superuser)).json()
    other_id = next(u["id"] for u in users if u["email"] == "second@test.ru")
    resp = client.post(
        f"/api/admin/users/{other_id}/status", json={"status": "blocked"}, headers=auth(superuser)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"


# ---------------------------------------------------------------------------
# REGRESSION: org_admin без is_superuser не должен видеть /api/admin/users
# (закрываем межорганизационную утечку)
# ---------------------------------------------------------------------------

def test_org_admin_cannot_list_global_users(client, db_session):
    """org_admin (не superuser) получает 403 на глобальном /api/admin/users.

    Регрессионный тест: до фикса require_admin пускал org_admin, что давало
    одному org_admin доступ к пользователям всех других организаций.
    """
    # Сначала регистрируем superuser, чтобы наш org_admin не стал первым
    make_user(client, "superuser@test.ru")
    hdr = _org_admin_hdr(db_session)
    resp = client.get("/api/admin/users", headers=hdr)
    assert resp.status_code == 403, (
        "org_admin (не superuser) должен получать 403 на /api/admin/users "
        "чтобы не допустить чтения пользователей чужих организаций"
    )


def test_org_admin_cannot_change_status_globally(client, db_session):
    """org_admin не может изменить статус пользователя через глобальный эндпоинт."""
    make_user(client, "superuser@test.ru")
    hdr = _org_admin_hdr(db_session)
    resp = client.post(
        "/api/admin/users/1/status", json={"status": "blocked"}, headers=hdr
    )
    assert resp.status_code == 403
