"""
CSRF middleware (double-submit) — тесты Task 2.

Стратегия выбора endpoint:
  - POST /api/clients  — мутирующий, требует только require_active (не superuser).
    Подходит для проверки CSRF: middleware срабатывает до route-авторизации.
  - PUT /api/profile   — мутирующий, доступен Bearer-токеном без cookie.
    Используется для проверки, что Bearer-путь не CSRF-блокируется.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth.models import User
from app.core.security import create_access_token, hash_password
from app.orgs.models import Organization


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _setup_user(db_session, email="csrf@test.ru", password="Pass12345"):
    org = Organization(name="CSRFOrg")
    db_session.add(org)
    db_session.commit()
    u = User(
        email=email, name="CsrfUser",
        role="org_admin", status="active",
        org_id=org.id,
        password_hash=hash_password(password),
    )
    db_session.add(u)
    db_session.commit()
    return u


def _bearer_headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


# ---------------------------------------------------------------------------
# тесты
# ---------------------------------------------------------------------------

def test_csrf_blocks_cookie_auth_mutation_without_header(client, db_session):
    """Cookie-аутентифицированный POST без X-CSRF-Token → 403 от middleware."""
    _setup_user(db_session)
    # логинимся → cookie jar TestClient получает access_token + csrf_token
    login_r = client.post(
        "/api/auth/login", json={"email": "csrf@test.ru", "password": "Pass12345"}
    )
    assert login_r.status_code == 200

    # шлём мутирующий запрос БЕЗ CSRF-заголовка
    r = client.post("/api/clients", json={"name": "ООО Тест", "phone": ""})
    assert r.status_code == 403
    assert "CSRF" in r.json().get("detail", "")


def test_csrf_allows_cookie_auth_mutation_with_correct_header(client, db_session):
    """Cookie-аутентифицированный POST с верным X-CSRF-Token → не 403 (проходит middleware)."""
    _setup_user(db_session)
    login_r = client.post(
        "/api/auth/login", json={"email": "csrf@test.ru", "password": "Pass12345"}
    )
    assert login_r.status_code == 200

    csrf = client.cookies.get("csrf_token")
    assert csrf, "csrf_token cookie должна быть установлена после логина"

    # шлём мутирующий запрос С CSRF-заголовком
    r = client.post(
        "/api/clients",
        json={"name": "ООО Тест", "phone": ""},
        headers={"X-CSRF-Token": csrf},
    )
    # middleware пропустил — ответ не должен быть 403 с CSRF-деталью
    assert r.status_code != 403 or "CSRF" not in r.json().get("detail", "")


def test_csrf_not_applied_to_bearer_auth(client, db_session):
    """Bearer-аутентифицированная мутация без CSRF-заголовка → не 403 (иммунитет)."""
    u = _setup_user(db_session)
    # используем Bearer, cookie НЕТ
    headers = _bearer_headers(u)
    payload = {
        "org_name": "Bearer Org",
        "inn": "",
        "contacts": {},
        "bank_requisites": "",
        "utp": [],
        "cases": [],
        "guarantee": "",
        "logo_url": "",
    }
    r = client.put("/api/profile", json=payload, headers=headers)
    # middleware не должен заблокировать (нет access_token cookie)
    assert r.status_code != 403 or "CSRF" not in r.json().get("detail", "")
