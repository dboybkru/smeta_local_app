# Инвайт по email-ссылке (invite-only онбординг) — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). Tasks sequential. Зависит от B (set_auth_cookies, _user_out уже есть).

**Goal:** Инвайт генерит токен-ссылку, шлёт письмо (SMTP); приглашённый на `/invite/{token}` ставит имя+пароль → active в своей орг/роли → залогинен (cookie). Открытый register — только бутстрап первого юзера.

**Architecture:** `User.invite_token`+`invite_expires_at`; `app/email/` (EmailSender, SMTP из app_settings, graceful); инвайт-эндпоинт шлёт письмо и возвращает `email_sent`+`invite_link`; `GET/POST /api/auth/invite/{token}` для приёма; фронт `/invite/:token`.

**Tech Stack:** FastAPI + smtplib + pytest (EmailSender замокан); React + Vitest. Миграция: down_revision = `f7a8b9c0d1e2` (миграция A; B без миграции).

**Спек:** `docs/superpowers/specs/2026-06-16-email-invite-onboarding-design.md`

**Команды:** backend `./.venv/Scripts/python.exe -m pytest -q`, `./.venv/Scripts/ruff.exe check .`; frontend `npm run test/build/lint`.

---

## Структура файлов
- Создать: `backend/app/email/__init__.py`, `backend/app/email/sender.py`; миграция `backend/alembic/versions/a8b9c0d1e2f3_invite_token.py`; `frontend/src/pages/InvitePage.tsx`.
- Изменить: `backend/app/auth/models.py` (User +invite_token/expires), `backend/app/settings/router.py` (SMTP), `backend/app/orgs/router.py` (invite шлёт письмо + resend), `backend/app/auth/router.py` (invite info/accept + register bootstrap-only), `backend/app/orgs/schemas.py` (ответы), `frontend/src/App.tsx` (route), `frontend/src/pages/LoginPage.tsx` (подсказка), `frontend/src/pages/OrgsPage.tsx` (link/resend), `frontend/src/api/orgs.ts`+`settings.ts`, `frontend/src/pages/AiConfigPage.tsx` (SMTP-секция).
- Тесты: `backend/tests/test_email_sender.py`, `test_invite_flow.py`, `test_settings_smtp.py`; правки `test_onboarding.py`; фронт `InvitePage.test.tsx`.

---

## Task 1: User.invite_token + миграция

**Files:** Modify `backend/app/auth/models.py`. Create migration. Test `backend/tests/test_invite_flow.py` (заготовка).

- [ ] **Step 1: Failing test** — `backend/tests/test_invite_flow.py`:
```python
from datetime import UTC, datetime, timedelta

from app.auth.models import User
from app.orgs.models import Organization


def test_user_has_invite_token_columns(db_session):
    o = Organization(name="IT"); db_session.add(o); db_session.commit()
    u = User(email="i@x.ru", name="", role="estimator", status="invited", org_id=o.id,
             invite_token="tok123", invite_expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    assert u.invite_token == "tok123" and u.invite_expires_at is not None
```

- [ ] **Step 2: Run → FAIL** `./.venv/Scripts/python.exe -m pytest tests/test_invite_flow.py::test_user_has_invite_token_columns -q` (нет полей).

- [ ] **Step 3: Модель.** В `backend/app/auth/models.py` добавить в класс `User` (проверь импорт `DateTime`, `String` есть; добавить при нужде):
```python
    invite_token: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```
(добавить `from datetime import datetime` если нет.)

- [ ] **Step 4: Миграция** `backend/alembic/versions/a8b9c0d1e2f3_invite_token.py` (импорты отсортированы):
```python
"""user.invite_token + invite_expires_at

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("invite_token", sa.String(length=64), nullable=True))
    op.add_column(
        "users", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_users_invite_token", "users", ["invite_token"])


def downgrade() -> None:
    op.drop_index("ix_users_invite_token", table_name="users")
    op.drop_column("users", "invite_expires_at")
    op.drop_column("users", "invite_token")
```

- [ ] **Step 5: Run** `./.venv/Scripts/python.exe -m pytest tests/test_invite_flow.py -q` → PASS. Lint `./.venv/Scripts/ruff.exe check .` чисто.

- [ ] **Step 6: Commit**
```bash
git add backend/app/auth/models.py backend/alembic/versions/a8b9c0d1e2f3_invite_token.py backend/tests/test_invite_flow.py
git commit -m "feat(auth): User.invite_token + invite_expires_at + миграция"
```

---

## Task 2: Email-модуль (SMTP)

**Files:** Create `backend/app/email/__init__.py`, `backend/app/email/sender.py`. Test `backend/tests/test_email_sender.py`.

- [ ] **Step 1: Failing test** `backend/tests/test_email_sender.py`:
```python
import pytest

from app.email import sender
from app.settings import service as ss


def test_send_email_not_configured_raises(db_session):
    with pytest.raises(sender.EmailNotConfigured):
        sender.send_email(db_session, "to@x.ru", "S", "<b>h</b>", "h")


def test_send_email_uses_transport(db_session):
    ss.set_secret(db_session, sender.SMTP_HOST, "smtp.test")
    ss.set_secret(db_session, sender.SMTP_PORT, "587")
    ss.set_secret(db_session, sender.SMTP_USER, "u@x.ru")
    ss.set_secret(db_session, sender.SMTP_PASSWORD, "pw")
    ss.set_secret(db_session, sender.SMTP_FROM, "from@x.ru")
    ss.set_secret(db_session, sender.SMTP_TLS, "true")
    sent = {}

    class FakeSMTP:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent["tls"] = True
        def login(self, u, p): sent["login"] = (u, p)
        def sendmail(self, frm, to, msg): sent["mail"] = (frm, to, msg)

    sender.send_email(db_session, "to@x.ru", "Subj", "<b>h</b>", "h", _transport=FakeSMTP())
    assert sent["login"] == ("u@x.ru", "pw")
    assert sent["mail"][0] == "from@x.ru" and sent["mail"][1] == ["to@x.ru"]
    assert "Subj" in sent["mail"][2]
```

- [ ] **Step 2: Run → FAIL** (модуля нет).

- [ ] **Step 3: `app/email/__init__.py`** пустой. **`app/email/sender.py`:**
```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.settings import service as settings_service

SMTP_HOST = "smtp_host"
SMTP_PORT = "smtp_port"
SMTP_USER = "smtp_user"
SMTP_PASSWORD = "smtp_password"
SMTP_FROM = "smtp_from"
SMTP_TLS = "smtp_tls"


class EmailNotConfigured(Exception):
    pass


class EmailError(Exception):
    pass


def _config(db: Session) -> dict:
    host = settings_service.get_secret(db, SMTP_HOST)
    if not host:
        raise EmailNotConfigured()
    user = settings_service.get_secret(db, SMTP_USER)
    return {
        "host": host,
        "port": int(settings_service.get_secret(db, SMTP_PORT) or "587"),
        "user": user,
        "password": settings_service.get_secret(db, SMTP_PASSWORD),
        "from": settings_service.get_secret(db, SMTP_FROM) or user,
        "tls": (settings_service.get_secret(db, SMTP_TLS) or "true").lower() != "false",
    }


def send_email(db: Session, to: str, subject: str, html: str, text: str, _transport=None) -> None:
    cfg = _config(db)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        smtp = _transport or smtplib.SMTP(cfg["host"], cfg["port"], timeout=10)
        with smtp:
            if cfg["tls"]:
                smtp.starttls()
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.sendmail(cfg["from"], [to], msg.as_string())
    except (EmailNotConfigured, EmailError):
        raise
    except Exception as exc:  # noqa: BLE001 — любая ошибка SMTP → EmailError
        raise EmailError(str(exc)) from exc


def send_invite_email(db: Session, to: str, org_name: str, link: str, _transport=None) -> None:
    subject = "Приглашение в SmetaApp"
    text = (
        f"Вас пригласили в организацию «{org_name}» в SmetaApp.\n"
        f"Перейдите по ссылке (действует 7 дней), чтобы задать пароль и войти:\n{link}\n"
    )
    html = (
        f"<p>Вас пригласили в организацию «{org_name}» в SmetaApp.</p>"
        f"<p>Перейдите по ссылке (действует 7 дней), чтобы задать пароль и войти:</p>"
        f'<p><a href="{link}">{link}</a></p>'
    )
    send_email(db, to, subject, html, text, _transport=_transport)
```

- [ ] **Step 4: Run** `./.venv/Scripts/python.exe -m pytest tests/test_email_sender.py -q` → PASS. Lint чисто.

- [ ] **Step 5: Commit**
```bash
git add backend/app/email backend/tests/test_email_sender.py
git commit -m "feat(email): EmailSender (SMTP из app_settings) + send_invite_email"
```

---

## Task 3: SMTP-настройки (superuser)

**Files:** Modify `backend/app/settings/router.py`. Test `backend/tests/test_settings_smtp.py`.

- [ ] **Step 1: Failing test** `backend/tests/test_settings_smtp.py` (зеркало `test_settings.py` — прочитать его для хелпера `_admin` с `is_superuser=True` и формата клиента):
```python
# arrange: superuser (is_superuser=True) + _hdr; зеркалить существующий test_settings.py
def test_smtp_put_get_roundtrip(client, db_session):
    su = _superuser(db_session)
    r = client.put("/api/settings/smtp", json={
        "host": "smtp.test", "port": "587", "user": "u@x.ru",
        "password": "secret", "from_addr": "from@x.ru", "tls": "true",
    }, headers=_hdr(su))
    assert r.status_code == 200
    g = client.get("/api/settings/smtp", headers=_hdr(su)).json()
    assert g["host"] == "smtp.test" and g["has_password"] is True
    # пароль не возвращается в открытом виде
    assert "password" not in g or g.get("password") in (None, "")


def test_smtp_requires_superuser(client, db_session):
    oa = _org_admin(db_session)  # org_admin, не superuser
    assert client.get("/api/settings/smtp", headers=_hdr(oa)).status_code == 403
```
(Хелперы `_superuser`/`_org_admin`/`_hdr` — взять как в `test_settings.py`/`test_settings_yandex.py`.)

- [ ] **Step 2: Run → FAIL** (эндпоинтов нет).

- [ ] **Step 3: Реализация** в `backend/app/settings/router.py` (добавить ключи, схему, GET/PUT — зеркало dadata/yandex):
```python
SMTP_KEYS = {
    "host": "smtp_host", "port": "smtp_port", "user": "smtp_user",
    "from_addr": "smtp_from", "tls": "smtp_tls",
}
SMTP_PASSWORD = "smtp_password"


class SmtpIn(BaseModel):
    host: str = ""
    port: str = ""
    user: str = ""
    password: str = ""
    from_addr: str = ""
    tls: str = ""


def _smtp_status(db: Session) -> dict:
    out = {field: service.get_secret(db, key) for field, key in SMTP_KEYS.items()}
    out["has_password"] = service.has_secret(db, SMTP_PASSWORD)
    return out


@router.get("/smtp", dependencies=[Depends(require_superuser)])
def get_smtp(db: Session = Depends(get_db)):
    return _smtp_status(db)


@router.put("/smtp")
def set_smtp(body: SmtpIn, db: Session = Depends(get_db), _: object = Depends(require_superuser)):
    for field, key in SMTP_KEYS.items():
        val = getattr(body, field).strip()
        if val:
            service.set_secret(db, key, val)
    if body.password.strip():
        service.set_secret(db, SMTP_PASSWORD, body.password.strip())
    return _smtp_status(db)
```

- [ ] **Step 4: Run** `./.venv/Scripts/python.exe -m pytest tests/test_settings_smtp.py -q` → PASS. Lint чисто.

- [ ] **Step 5: Commit**
```bash
git add backend/app/settings/router.py backend/tests/test_settings_smtp.py
git commit -m "feat(settings): SMTP-конфиг /api/settings/smtp (superuser, пароль write-only)"
```

---

## Task 4: Инвайт шлёт письмо + resend

**Files:** Modify `backend/app/orgs/router.py`, `backend/app/orgs/schemas.py`. Test дополняет `backend/tests/test_invite_flow.py`.

- [ ] **Step 1: Failing test** — в `backend/tests/test_invite_flow.py` добавить (мокая письмо через monkeypatch `app.email.sender.send_invite_email`):
```python
import app.email.sender as email_sender
from app.auth.models import User as U
from app.core.security import create_access_token


def _su(db):
    o = Organization(name="INV"); db.add(o); db.commit()
    su = U(email="suinv@x.ru", name="S", role="org_admin", status="active",
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
    u = db_session.scalars(__import__("sqlalchemy").select(U).where(U.email == "new@x.ru")).one()
    assert u.invite_token and u.invite_expires_at and calls["to"] == "new@x.ru"


def test_invite_graceful_when_email_unconfigured(client, db_session, monkeypatch):
    su, o = _su(db_session)
    def _raise(*a, **k): raise email_sender.EmailNotConfigured()
    monkeypatch.setattr(email_sender, "send_invite_email", _raise)
    r = client.post(f"/api/orgs/{o.id}/users", json={"email": "n2@x.ru", "role": "viewer"},
                    headers=_h(su))
    assert r.status_code == 201 and r.json()["email_sent"] is False
    assert "/invite/" in r.json()["invite_link"]  # ссылку показываем админу
```

- [ ] **Step 2: Run → FAIL** (ответ без email_sent/invite_link; токен не генерится).

- [ ] **Step 3: Реализация** в `backend/app/orgs/router.py` `invite_user` — после `db.refresh(u)` добавить генерацию токена и отправку (импорты вверху: `import secrets`, `from datetime import UTC, datetime, timedelta`, `from app.core.config import settings`, `from app.email import sender as email_sender`):
```python
    u.invite_token = secrets.token_urlsafe(32)
    u.invite_expires_at = datetime.now(UTC) + timedelta(days=7)
    db.commit()
    db.refresh(u)
    org = db.get(Organization, org_id)
    link = f"{settings.frontend_url}/invite/{u.invite_token}"
    email_sent = False
    try:
        email_sender.send_invite_email(db, u.email, org.name if org else "", link)
        email_sent = True
    except (email_sender.EmailNotConfigured, email_sender.EmailError):
        email_sent = False
    return {"id": u.id, "email": u.email, "role": u.role, "status": u.status,
            "email_sent": email_sent, "invite_link": link}
```

- [ ] **Step 4: Resend-эндпоинт** в `backend/app/orgs/router.py`:
```python
@router.post("/{org_id}/users/{uid}/resend-invite")
def resend_invite(
    org_id: int,
    uid: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_org_admin),
):
    if not actor.is_superuser and actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="Чужая организация")
    u = db.get(User, uid)
    if u is None or u.org_id != org_id or u.status != "invited":
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    u.invite_token = secrets.token_urlsafe(32)
    u.invite_expires_at = datetime.now(UTC) + timedelta(days=7)
    db.commit()
    org = db.get(Organization, org_id)
    link = f"{settings.frontend_url}/invite/{u.invite_token}"
    email_sent = False
    try:
        email_sender.send_invite_email(db, u.email, org.name if org else "", link)
        email_sent = True
    except (email_sender.EmailNotConfigured, email_sender.EmailError):
        email_sent = False
    return {"id": u.id, "email": u.email, "status": u.status,
            "email_sent": email_sent, "invite_link": link}
```
Добавить тест resend (перевыпуск токена, 404 для не-invited).

- [ ] **Step 5: Run** `./.venv/Scripts/python.exe -m pytest tests/test_invite_flow.py -q` → PASS. Lint чисто.

- [ ] **Step 6: Commit**
```bash
git add backend/app/orgs/router.py backend/app/orgs/schemas.py backend/tests/test_invite_flow.py
git commit -m "feat(orgs): инвайт генерит токен и шлёт письмо (graceful) + resend-invite"
```

---

## Task 5: Claim-эндпоинты + register bootstrap-only

**Files:** Modify `backend/app/auth/router.py`, `backend/app/auth/schemas.py`. Test дополняет `test_invite_flow.py`, правит `test_onboarding.py`.

- [ ] **Step 1: Failing test** — в `test_invite_flow.py`:
```python
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
    u = db_session.scalars(__import__("sqlalchemy").select(U).where(U.email == "ac@x.ru")).one()
    assert u.status == "active" and u.invite_token is None and u.password_hash
    # повторный accept → 404 (токен погашен)
    assert client.post(f"/api/auth/invite/{token}/accept",
                       json={"name": "X", "password": "Pass12345"}).status_code == 404


def test_register_invite_only_when_users_exist(client, db_session):
    _su(db_session)  # юзеры уже есть
    r = client.post("/api/auth/register",
                    json={"email": "open@x.ru", "password": "Pass12345", "name": "O"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run → FAIL**.

- [ ] **Step 3: Schemas.** В `backend/app/auth/schemas.py` добавить:
```python
class InviteAcceptIn(BaseModel):
    name: str = ""
    password: str = Field(min_length=8)
```

- [ ] **Step 4: Эндпоинты** в `backend/app/auth/router.py` (импорты: `from datetime import UTC, datetime`, `from sqlalchemy import func, select`, `from app.auth.schemas import InviteAcceptIn`, `hash_password` из security):
```python
@router.get("/invite/{token}")
def invite_info(token: str, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.invite_token == token))
    if u is None or u.status != "invited":
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    if u.invite_expires_at and u.invite_expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Срок приглашения истёк")
    org = db.get(Organization, u.org_id) if u.org_id else None
    return {"email": u.email, "org_name": org.name if org else None, "role": u.role}


@router.post("/invite/{token}/accept", response_model=UserOut)
def invite_accept(
    token: str, body: InviteAcceptIn, response: Response, db: Session = Depends(get_db)
):
    u = db.scalar(select(User).where(User.invite_token == token))
    if u is None or u.status != "invited":
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    if u.invite_expires_at and u.invite_expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Срок приглашения истёк")
    u.password_hash = hash_password(body.password)
    u.name = body.name or u.name
    u.status = "active"
    u.invite_token = None
    u.invite_expires_at = None
    db.commit()
    db.refresh(u)
    t = service.issue_tokens(u)
    set_auth_cookies(response, t["access_token"], t["refresh_token"])
    return _user_out(db, u)
```
ПЛЮС CSRF-exempt: в `backend/app/main.py` добавить в `_CSRF_EXEMPT`-логику пути инвайта. Поскольку пути динамические (`/api/auth/invite/{token}/accept`), заменить точную проверку для них на префикс: в middleware добавить условие `or path.startswith("/api/auth/invite/")` в исключения (accept без сессии — cookie-аутентификации нет, но для надёжности исключаем явно).

- [ ] **Step 5: register bootstrap-only.** В `backend/app/auth/router.py` `register` — в начале:
```python
    if db.scalar(select(func.count()).select_from(User)):
        raise HTTPException(status_code=403, detail="Регистрация только по приглашению")
```
(перед вызовом `service.register_user`). Так открытая регистрация работает лишь когда юзеров нет (бутстрап первого superuser).

- [ ] **Step 6: Правка `test_onboarding.py`.** Старые кейсы под новую политику: `test_register_claims_invited` → заменить на токен-accept-флоу (или удалить — покрыто `test_invite_flow`); `test_self_register_without_invite_is_pending_orgless` → теперь ожидает 403. `test_invite_creates_invited_user` остаётся (но теперь ответ содержит email_sent/invite_link — поправить ассерты при необходимости; письмо замокать). Прогнать `tests/test_onboarding.py tests/test_invite_flow.py` до зелёного.

- [ ] **Step 7: Run** `./.venv/Scripts/python.exe -m pytest -q` (полный) → зелёное. Lint `./.venv/Scripts/ruff.exe check .` чисто.

- [ ] **Step 8: Commit**
```bash
git add backend/app/auth backend/app/main.py backend/tests
git commit -m "feat(auth): приём инвайта /invite/{token} (info+accept) + register только бутстрап"
```

---

## Task 6: Фронтенд — InvitePage + login-подсказка + invite-form link/resend + SMTP UI

**Files:** Create `frontend/src/pages/InvitePage.tsx`. Modify `frontend/src/App.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/OrgsPage.tsx`, `frontend/src/api/orgs.ts`, `frontend/src/api/settings.ts`, `frontend/src/pages/AiConfigPage.tsx`. Tests: `InvitePage.test.tsx` + правки.

- [ ] **Step 1: api/orgs.ts.** Обновить тип ответа `inviteUser` на `{ id; email; role; status; email_sent: boolean; invite_link: string }`; добавить `resendInvite(orgId, uid)` (POST `/orgs/{orgId}/users/{uid}/resend-invite`). Добавить (api/auth или новый) `getInvite(token)` → GET `/auth/invite/{token}`; `acceptInvite(token, {name, password})` → POST `/auth/invite/{token}/accept`. (Используй `api()`.)

- [ ] **Step 2: InvitePage.tsx** (`/invite/:token`): на mount `getInvite(token)` → если ок, показать «Вас пригласили в {org_name} как {role}», форма name+password → `acceptInvite` → `reload()` (из useAuth) → `navigate("/")`. 404 → «Приглашение не найдено», 410 → «Срок истёк». Стиль — как LoginPage (центрированная карточка). Добавить smoke-тест `InvitePage.test.tsx` (мок api: загрузка инфо, успешный accept, истёкший токен).

- [ ] **Step 3: App.tsx route.** Добавить `<Route path="/invite/:token" element={<InvitePage />} />` ВНЕ `RequireAuth` (как `/login`).

- [ ] **Step 4: LoginPage.** Под формой добавить строку-подсказку: `<p className="text-center text-sm text-stone-400">Нет аккаунта? Попросите приглашение у администратора.</p>`.

- [ ] **Step 5: OrgsPage invite-form.** После создания инвайта показать `invite_link`, если `email_sent === false` (блок с копированием ссылки) либо тост «письмо отправлено». В списке пользователей у `status === "invited"` — кнопка «Переотправить» → `resendInvite` → снова показать link/статус. Обновить `OrgsPage.test.tsx` под новый ответ.

- [ ] **Step 6: SMTP UI.** В `frontend/src/api/settings.ts` добавить `getSmtp()`/`setSmtp(body)` (GET/PUT `/settings/smtp`). В `AiConfigPage.tsx` добавить секцию «SMTP (отправка почты)» рядом с DaData/Яндекс (поля host/port/user/password/from/tls, password write-only — `has_password`), superuser-only. Зеркалить существующие секции настроек.

- [ ] **Step 7: Run** (из `frontend`) `npm run test` зелёное, `npm run build` ок, `npm run lint` 0 ошибок.

- [ ] **Step 8: Commit**
```bash
git add frontend/src
git commit -m "feat(ui): приём инвайта /invite/:token + invite-link/resend + SMTP-настройки + login-подсказка"
```

---

## Финальная проверка
- [ ] Backend `pytest -q` + `ruff check .` зелёные; фронт `npm run test`/`build`/`lint` зелёные.
- [ ] `alembic heads` → один head `a8b9c0d1e2f3`; цепочка `…→ f7a8b9c0d1e2 → a8b9c0d1e2f3`.
- [ ] Холистическое ревью (субагентно): claim гасит токен (повтор → 404), просрочка → 410, accept ставит cookie-сессию; invite graceful без SMTP (email_sent=false + link); register invite-only кроме бутстрапа; EmailSender нигде не шлёт реально в тестах (замокан); CSRF не мешает accept (без сессии).
- [ ] Пред-условие прод (на пользователе): SMTP-креды в `/admin/ai` → SMTP + SPF/DKIM/DMARC на `smetaapp.ru`.
