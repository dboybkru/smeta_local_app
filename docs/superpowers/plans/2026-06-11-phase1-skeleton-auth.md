# SmetaApp Phase 1 — каркас и авторизация: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Рабочий каркас SmetaApp: FastAPI-бэкенд с авторизацией (Яндекс OAuth + email/пароль, JWT, роли, pending-аппрув), минимальный React-фронтенд с входом и админкой пользователей, Docker Compose, миграции, CI.

**Architecture:** Модульный FastAPI (`app/core`, `app/auth`, скелеты остальных модулей), PostgreSQL через SQLAlchemy 2.0 + Alembic, JWT (access 30 мин / refresh 30 дней, stateless). Frontend — React 19 + Vite + TypeScript + Tailwind v4, токены в localStorage, прокси `/api` на бэкенд. Прод — Docker Compose: postgres + backend + caddy со статикой фронта.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, psycopg3, PyJWT, argon2-cffi, httpx/respx, pytest, ruff; Node 22, React 19, Vite, react-router 7, Tailwind v4, vitest; Docker Compose, Caddy, GitHub Actions.

**Working directory:** `D:\git\smeta_local_app`. Перед началом: `git checkout -b phase-1-skeleton-auth`.

**Спека:** `docs/superpowers/specs/2026-06-11-smeta-app-design.md` (§3 структура, §4 User, §8 авторизация, §11 инфраструктура).

---

### Task 1: Скелет бэкенда + health endpoint

**Files:**
- Create: `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/ruff.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/tests/__init__.py`, `backend/tests/test_health.py`, `.gitignore`

- [ ] **Step 1: Зависимости и конфиг линтера**

`backend/requirements.txt`:
```
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
alembic>=1.13
psycopg[binary]>=3.2
pydantic>=2.7
pydantic-settings>=2.3
email-validator>=2.1
PyJWT>=2.8
argon2-cffi>=23.1
httpx>=0.27
```

`backend/requirements-dev.txt`:
```
pytest>=8
respx>=0.21
ruff>=0.5
```

`backend/ruff.toml`:
```toml
line-length = 100
target-version = "py312"
```

`.gitignore` (корень репо):
```
__pycache__/
*.pyc
.venv/
venv/
.env
node_modules/
dist/
.pytest_cache/
.ruff_cache/
```

Установка (из `backend/`):
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
```

- [ ] **Step 2: Failing test для health**

`backend/tests/test_health.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

`backend/tests/__init__.py` и `backend/app/__init__.py` — пустые файлы.

- [ ] **Step 3: Запустить тест — убедиться, что падает**

Run (из `backend/`): `.venv\Scripts\python -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 4: Минимальная реализация**

`backend/app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="SmetaApp API")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Тест зелёный**

Run: `.venv\Scripts\python -m pytest tests/test_health.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add .gitignore backend/
git commit -m "feat(backend): скелет FastAPI + /api/health"
```

---

### Task 2: Конфиг и подключение к БД

**Files:**
- Create: `backend/app/core/__init__.py`, `backend/app/core/config.py`, `backend/app/core/db.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Failing test**

`backend/tests/test_config.py`:
```python
from app.core.config import settings


def test_settings_defaults():
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.access_token_ttl_minutes == 30
    assert settings.refresh_token_ttl_days == 30
```

- [ ] **Step 2: Run — FAIL** (`ModuleNotFoundError: app.core.config`)

Run: `.venv\Scripts\python -m pytest tests/test_config.py -v`

- [ ] **Step 3: Реализация**

`backend/app/core/__init__.py` — пустой.

`backend/app/core/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-change-me"
    database_url: str = "postgresql+psycopg://smeta:smeta@localhost:5432/smeta"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    yandex_client_id: str = ""
    yandex_client_secret: str = ""
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"


settings = Settings()
```

`backend/app/core/db.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: Run — PASS**, затем весь набор: `.venv\Scripts\python -m pytest -q` — все зелёные.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core backend/tests/test_config.py
git commit -m "feat(backend): настройки pydantic-settings и сессия БД"
```

---

### Task 3: Модель User + Alembic

**Files:**
- Create: `backend/app/auth/__init__.py`, `backend/app/auth/models.py`, `backend/alembic.ini`, `backend/alembic/…`
- Test: `backend/tests/conftest.py`, `backend/tests/test_user_model.py`

- [ ] **Step 1: Тестовая инфраструктура (conftest)**

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    with TestingSession() as session:
        yield session


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

Примечание: юнит-тесты идут на SQLite in-memory ради скорости. Postgres-специфичные типы появятся в фазе 2 — тогда добавим вариантные типы (`JSON().with_variant(JSONB, "postgresql")`) или Postgres-контейнер в тестах.

- [ ] **Step 2: Failing test модели**

`backend/tests/test_user_model.py`:
```python
from app.auth.models import User


def test_user_defaults(db_session):
    user = User(email="a@b.ru", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.id is not None
    assert user.role == "estimator"
    assert user.status == "pending"
    assert user.yandex_id is None
    assert user.created_at is not None
```

- [ ] **Step 3: Run — FAIL** (`ModuleNotFoundError: app.auth.models`)

- [ ] **Step 4: Реализация модели**

`backend/app/auth/__init__.py` — пустой.

`backend/app/auth/models.py`:
```python
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

ROLES = ("admin", "estimator", "viewer")
STATUSES = ("pending", "active", "blocked")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    yandex_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="estimator")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 5: Run — PASS**

- [ ] **Step 6: Alembic init и первая миграция**

Из `backend/`:
```powershell
.venv\Scripts\alembic init alembic
```

В `backend/alembic/env.py` после строки `config = context.config` добавить:
```python
from app.core.config import settings
from app.core.db import Base
from app.auth import models  # noqa: F401  — регистрирует таблицы в metadata

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```
(заменив существующую строку `target_metadata = None`).

Поднять локальный Postgres для генерации миграции (нужен docker; если compose ещё не создан — задача 11, можно временно):
```powershell
docker run -d --name smeta-pg-tmp -e POSTGRES_USER=smeta -e POSTGRES_PASSWORD=smeta -e POSTGRES_DB=smeta -p 5432:5432 postgres:16-alpine
.venv\Scripts\alembic revision --autogenerate -m "users table"
.venv\Scripts\alembic upgrade head
```
Expected: файл в `backend/alembic/versions/` с `create_table('users', …)`; `upgrade head` без ошибок. Проверить содержимое миграции глазами: колонки соответствуют модели, есть уникальные индексы email и yandex_id.

- [ ] **Step 7: Commit**

```bash
git add backend/app/auth backend/tests backend/alembic backend/alembic.ini
git commit -m "feat(auth): модель User + alembic с первой миграцией"
```

---

### Task 4: Безопасность — argon2 и JWT

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_security.py`:
```python
import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_access_token_roundtrip():
    token = create_access_token(user_id=7, role="admin")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "7"
    assert payload["role"] == "admin"


def test_refresh_token_type_enforced():
    token = create_refresh_token(user_id=7, role="admin")
    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type="access")


def test_garbage_token_rejected():
    with pytest.raises(InvalidTokenError):
        decode_token("garbage", expected_type="access")
```

- [ ] **Step 2: Run — FAIL** (`ModuleNotFoundError`)

- [ ] **Step 3: Реализация**

`backend/app/core/security.py`:
```python
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _create_token(user_id: int, role: str, token_type: str, ttl: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    return _create_token(
        user_id, role, "access", timedelta(minutes=settings.access_token_ttl_minutes)
    )


def create_refresh_token(user_id: int, role: str) -> str:
    return _create_token(user_id, role, "refresh", timedelta(days=settings.refresh_token_ttl_days))


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"expected {expected_type} token")
    return payload
```

- [ ] **Step 4: Run — PASS** (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(core): хеширование argon2 + JWT access/refresh"
```

---

### Task 5: Регистрация и вход по email/паролю

**Files:**
- Create: `backend/app/auth/schemas.py`, `backend/app/auth/service.py`, `backend/app/auth/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth_register_login.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_auth_register_login.py`:
```python
def register(client, email="user@test.ru", password="secret123", name="Тест"):
    return client.post(
        "/api/auth/register", json={"email": email, "password": password, "name": name}
    )


def test_first_user_becomes_active_admin(client):
    resp = register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "admin"
    assert body["status"] == "active"


def test_second_user_is_pending_estimator(client):
    register(client, email="first@test.ru")
    resp = register(client, email="second@test.ru")
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "estimator"
    assert body["status"] == "pending"


def test_duplicate_email_rejected(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 409


def test_login_returns_token_pair(client):
    register(client)
    resp = client.post(
        "/api/auth/login", json={"email": "user@test.ru", "password": "secret123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_401(client):
    register(client)
    resp = client.post("/api/auth/login", json={"email": "user@test.ru", "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_email_401(client):
    resp = client.post("/api/auth/login", json={"email": "ghost@test.ru", "password": "x"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run — FAIL** (404 на /api/auth/register)

Run: `.venv\Scripts\python -m pytest tests/test_auth_register_login.py -v`

- [ ] **Step 3: Реализация**

`backend/app/auth/schemas.py`:
```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    role: str
    status: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

`backend/app/auth/service.py`:
```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


class EmailTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def register_user(db: Session, email: str, password: str, name: str) -> User:
    if db.scalar(select(User).where(User.email == email)):
        raise EmailTakenError(email)
    is_first = (db.scalar(select(func.count()).select_from(User)) or 0) == 0
    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        role="admin" if is_first else "estimator",
        status="active" if is_first else "pending",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError(email)
    return user


def issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id, user.role),
        "token_type": "bearer",
    }
```

`backend/app/auth/router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.schemas import LoginIn, RegisterIn, TokenPair, UserOut
from app.core.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    try:
        return service.register_user(db, body.email, body.password, body.name)
    except service.EmailTakenError:
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: Session = Depends(get_db)):
    try:
        user = service.authenticate(db, body.email, body.password)
    except service.InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    return service.issue_tokens(user)
```

`backend/app/main.py` — заменить целиком:
```python
from fastapi import FastAPI

from app.auth.router import router as auth_router

app = FastAPI(title="SmetaApp API")
app.include_router(auth_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run — PASS** (6 passed), затем `.venv\Scripts\python -m pytest -q` — всё зелёное.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(auth): регистрация (первый юзер - админ) и вход email/пароль"
```

---

### Task 6: Зависимости текущего пользователя, /me, refresh

**Files:**
- Create: `backend/app/auth/deps.py`
- Modify: `backend/app/auth/router.py`
- Test: `backend/tests/test_auth_me_refresh.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_auth_me_refresh.py`:
```python
def make_user(client, email="user@test.ru"):
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret123", "name": "Т"},
    )
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    return resp.json()


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_me_returns_current_user(client):
    tokens = make_user(client)
    resp = client.get("/api/auth/me", headers=auth(tokens))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@test.ru"


def test_me_without_token_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_garbage_token_401(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_refresh_returns_new_pair(client):
    tokens = make_user(client)
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_refresh_rejects_access_token(client):
    tokens = make_user(client)
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_pending_user_can_see_me(client):
    make_user(client, email="admin@test.ru")  # первый - админ
    tokens = make_user(client, email="second@test.ru")  # pending
    resp = client.get("/api/auth/me", headers=auth(tokens))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
```

- [ ] **Step 2: Run — FAIL** (404 на /api/auth/me)

- [ ] **Step 3: Реализация**

`backend/app/auth/deps.py`:
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.db import get_db
from app.core.security import InvalidTokenError, decode_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Нет токена")
    try:
        payload = decode_token(creds.credentials, expected_type="access")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


def require_active(user: User = Depends(get_current_user)) -> User:
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Аккаунт не активирован")
    return user


def require_admin(user: User = Depends(require_active)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Нужны права администратора")
    return user
```

В `backend/app/auth/router.py` добавить (импорты дополнить: `from pydantic import BaseModel`, `from app.auth.deps import get_current_user`, `from app.auth.models import User`, `from app.core.security import InvalidTokenError, decode_token`):
```python
class RefreshIn(BaseModel):
    refresh_token: str


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return service.issue_tokens(user)
```

- [ ] **Step 4: Run — PASS** (6 passed), полный прогон `pytest -q` зелёный.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth backend/tests/test_auth_me_refresh.py
git commit -m "feat(auth): /me, refresh, зависимости require_active/require_admin"
```

---

### Task 7: Яндекс OAuth

**Files:**
- Create: `backend/app/auth/yandex.py`
- Modify: `backend/app/auth/router.py`, `backend/app/auth/service.py`
- Test: `backend/tests/test_auth_yandex.py`

- [ ] **Step 1: Failing tests** (respx мокает HTTP Яндекса)

`backend/tests/test_auth_yandex.py`:
```python
import respx
from httpx import Response


def test_yandex_login_redirects_with_state(client):
    resp = client.get("/api/auth/yandex/login", follow_redirects=False)
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert location.startswith("https://oauth.yandex.ru/authorize")
    assert "state=" in location
    assert "yx_state" in resp.cookies


@respx.mock
def test_yandex_callback_creates_user_and_redirects(client):
    respx.post("https://oauth.yandex.ru/token").mock(
        return_value=Response(200, json={"access_token": "ya-token"})
    )
    respx.get("https://login.yandex.ru/info").mock(
        return_value=Response(
            200,
            json={"id": "yx-123", "default_email": "ya@yandex.ru", "real_name": "Ян Дексов"},
        )
    )
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)

    resp = client.get(
        f"/api/auth/yandex/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 307
    assert "#access_token=" in resp.headers["location"]

    # первый пользователь -> активный админ
    import urllib.parse

    fragment = urllib.parse.urlparse(resp.headers["location"]).fragment
    access = dict(p.split("=", 1) for p in fragment.split("&"))["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.json()["email"] == "ya@yandex.ru"
    assert me.json()["role"] == "admin"


def test_yandex_callback_bad_state_400(client):
    client.cookies.set("yx_state", "expected")
    resp = client.get(
        "/api/auth/yandex/callback?code=abc&state=tampered", follow_redirects=False
    )
    assert resp.status_code == 400


@respx.mock
def test_yandex_links_to_existing_email_account(client):
    client.post(
        "/api/auth/register",
        json={"email": "ya@yandex.ru", "password": "secret123", "name": "Т"},
    )
    respx.post("https://oauth.yandex.ru/token").mock(
        return_value=Response(200, json={"access_token": "ya-token"})
    )
    respx.get("https://login.yandex.ru/info").mock(
        return_value=Response(
            200, json={"id": "yx-777", "default_email": "ya@yandex.ru", "real_name": ""}
        )
    )
    login = client.get("/api/auth/yandex/login", follow_redirects=False)
    state = login.cookies["yx_state"]
    client.cookies.set("yx_state", state)
    resp = client.get(
        f"/api/auth/yandex/callback?code=abc&state={state}", follow_redirects=False
    )
    assert resp.status_code == 307
    # повторный вход тем же yandex_id не создаёт дубль — это проверяет сервисная логика
```

- [ ] **Step 2: Run — FAIL** (404)

- [ ] **Step 3: Реализация**

`backend/app/auth/yandex.py`:
```python
import httpx

from app.core.config import settings

AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
TOKEN_URL = "https://oauth.yandex.ru/token"
USERINFO_URL = "https://login.yandex.ru/info"


def build_authorize_url(state: str) -> str:
    from urllib.parse import urlencode

    params = urlencode(
        {
            "response_type": "code",
            "client_id": settings.yandex_client_id,
            "redirect_uri": f"{settings.backend_url}/api/auth/yandex/callback",
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{params}"


def exchange_code(code: str) -> str:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.yandex_client_id,
            "client_secret": settings.yandex_client_secret,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_userinfo(access_token: str) -> dict:
    resp = httpx.get(
        USERINFO_URL,
        params={"format": "json"},
        headers={"Authorization": f"OAuth {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()
```

В `backend/app/auth/service.py` добавить:
```python
def get_or_create_yandex_user(db: Session, info: dict) -> User:
    yandex_id = str(info["id"])
    email = info.get("default_email") or f"{yandex_id}@yandex.local"
    user = db.scalar(select(User).where(User.yandex_id == yandex_id))
    if user:
        return user
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.yandex_id = yandex_id
        db.commit()
        db.refresh(user)
        return user
    is_first = (db.scalar(select(func.count()).select_from(User)) or 0) == 0
    user = User(
        email=email,
        yandex_id=yandex_id,
        name=info.get("real_name") or "",
        role="admin" if is_first else "estimator",
        status="active" if is_first else "pending",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

В `backend/app/auth/router.py` добавить (импорты: `import secrets`, `from fastapi import Request`, `from fastapi.responses import RedirectResponse`, `from app.auth import yandex`, `from app.core.config import settings`):
```python
@router.get("/yandex/login")
def yandex_login():
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(yandex.build_authorize_url(state))
    resp.set_cookie("yx_state", state, max_age=600, httponly=True, samesite="lax")
    return resp


@router.get("/yandex/callback")
def yandex_callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    if not state or state != request.cookies.get("yx_state"):
        raise HTTPException(status_code=400, detail="Неверный state")
    token = yandex.exchange_code(code)
    info = yandex.fetch_userinfo(token)
    user = service.get_or_create_yandex_user(db, info)
    pair = service.issue_tokens(user)
    url = (
        f"{settings.frontend_url}/auth/callback"
        f"#access_token={pair['access_token']}&refresh_token={pair['refresh_token']}"
    )
    resp = RedirectResponse(url)
    resp.delete_cookie("yx_state")
    return resp
```

- [ ] **Step 4: Run — PASS** (4 passed), полный `pytest -q` зелёный, `ruff check .` чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth backend/tests/test_auth_yandex.py
git commit -m "feat(auth): вход через Яндекс ID (OAuth 2.0, state-cookie, линковка по email)"
```

---

### Task 8: Админка пользователей (API)

**Files:**
- Create: `backend/app/auth/admin_router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_users.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_admin_users.py`:
```python
def make_user(client, email):
    client.post(
        "/api/auth/register", json={"email": email, "password": "secret123", "name": "Т"}
    )
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    return resp.json()


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_admin_lists_users(client):
    admin = make_user(client, "admin@test.ru")
    make_user(client, "second@test.ru")
    resp = client.get("/api/admin/users", headers=auth(admin))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_non_admin_cannot_list_users(client):
    make_user(client, "admin@test.ru")
    second = make_user(client, "second@test.ru")
    resp = client.get("/api/admin/users", headers=auth(second))
    assert resp.status_code == 403


def test_admin_approves_pending_user(client):
    admin = make_user(client, "admin@test.ru")
    make_user(client, "second@test.ru")
    users = client.get("/api/admin/users", headers=auth(admin)).json()
    pending_id = next(u["id"] for u in users if u["status"] == "pending")
    resp = client.post(
        f"/api/admin/users/{pending_id}/status",
        json={"status": "active"},
        headers=auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_status_change_unknown_user_404(client):
    admin = make_user(client, "admin@test.ru")
    resp = client.post(
        "/api/admin/users/999/status", json={"status": "active"}, headers=auth(admin)
    )
    assert resp.status_code == 404


def test_invalid_status_rejected(client):
    admin = make_user(client, "admin@test.ru")
    resp = client.post(
        "/api/admin/users/1/status", json={"status": "superuser"}, headers=auth(admin)
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run — FAIL** (404)

- [ ] **Step 3: Реализация**

`backend/app/auth/admin_router.py`:
```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.auth.models import User
from app.auth.schemas import UserOut
from app.core.db import get_db

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


class StatusIn(BaseModel):
    status: Literal["active", "blocked"]


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.created_at)).all()


@router.post("/users/{user_id}/status", response_model=UserOut)
def set_status(user_id: int, body: StatusIn, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.status = body.status
    db.commit()
    db.refresh(user)
    return user
```

В `backend/app/main.py` добавить:
```python
from app.auth.admin_router import router as admin_router

app.include_router(admin_router)
```

- [ ] **Step 4: Run — PASS** (5 passed), полный прогон зелёный.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests/test_admin_users.py
git commit -m "feat(admin): список пользователей и смена статуса (одобрение/блокировка)"
```

---

### Task 9: Скелеты остальных модулей

**Files:**
- Create: `backend/app/catalog/__init__.py`, `backend/app/clients/__init__.py`, `backend/app/estimates/__init__.py`, `backend/app/export/__init__.py`, `backend/app/public/__init__.py`, `backend/app/ai/__init__.py`

- [ ] **Step 1: Создать пакеты**

Каждый `__init__.py` — однострочный докстринг по назначению модуля (из спеки §3), например `backend/app/catalog/__init__.py`:
```python
"""Каталог: прайсы поставщиков, импорт, маппинг колонок, версии, поиск. Фаза 2."""
```
Аналогично: clients («Клиенты и ценовые уровни. Фаза 3.»), estimates («Сметы, ветки, автоподбор работ. Фаза 3.»), export («Экспорт Excel/PDF, водяные знаки. Фаза 4.»), public («Публичные ссылки на КП. Фаза 4.»), ai («AI-ассистент. Фаза 5.»).

- [ ] **Step 2: Проверка** — `pytest -q` зелёный, `ruff check .` чистый.

- [ ] **Step 3: Commit**

```bash
git add backend/app
git commit -m "chore(backend): скелеты модулей catalog/clients/estimates/export/public/ai"
```

---

### Task 10: Фронтенд — каркас, API-клиент, авторизация

**Files:**
- Create: `frontend/` (Vite react-ts), `frontend/src/api/client.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/vite.config.ts`, `frontend/src/index.css`
- Test: `frontend/src/pages/LoginPage.test.tsx` (в Task 11)

- [ ] **Step 1: Скаффолд**

Из корня репо:
```powershell
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom tailwindcss @tailwindcss/vite
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom
```

- [ ] **Step 2: Конфиг Vite + Tailwind + vitest**

`frontend/vite.config.ts` — заменить целиком:
```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
```

`frontend/src/test-setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

`frontend/src/index.css` — заменить содержимое на:
```css
@import "tailwindcss";
```

В `frontend/package.json` в `scripts` добавить: `"test": "vitest run"`.

- [ ] **Step 3: API-клиент с refresh-on-401**

`frontend/src/api/client.ts`:
```ts
const BASE = "/api";

export function getTokens() {
  return {
    access: localStorage.getItem("access_token"),
    refresh: localStorage.getItem("refresh_token"),
  };
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function rawRequest(path: string, options: RequestInit = {}) {
  const { access } = getTokens();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (access) headers["Authorization"] = `Bearer ${access}`;
  return fetch(`${BASE}${path}`, { ...options, headers });
}

async function tryRefresh(): Promise<boolean> {
  const { refresh } = getTokens();
  if (!refresh) return false;
  const resp = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!resp.ok) return false;
  const body = await resp.json();
  setTokens(body.access_token, body.refresh_token);
  return true;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  let resp = await rawRequest(path, options);
  if (resp.status === 401 && (await tryRefresh())) {
    resp = await rawRequest(path, options);
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new ApiError(resp.status, body.detail ?? resp.statusText);
  }
  return resp.json();
}
```

- [ ] **Step 4: Контекст авторизации**

`frontend/src/auth/AuthContext.tsx`:
```tsx
import { createContext, useContext, useEffect, useState } from "react";
import { api, clearTokens, getTokens, setTokens } from "../api/client";

export type User = {
  id: number;
  email: string;
  name: string;
  role: string;
  status: string;
};

type AuthState = {
  user: User | null | undefined; // undefined = загрузка
  loginWithPassword: (email: string, password: string) => Promise<void>;
  acceptTokens: (access: string, refresh: string) => Promise<void>;
  logout: () => void;
};

const AuthCtx = createContext<AuthState>(null!);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  async function loadMe() {
    try {
      setUser(await api<User>("/auth/me"));
    } catch {
      clearTokens();
      setUser(null);
    }
  }

  useEffect(() => {
    if (getTokens().access) void loadMe();
    else setUser(null);
  }, []);

  async function loginWithPassword(email: string, password: string) {
    const pair = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setTokens(pair.access_token, pair.refresh_token);
    await loadMe();
  }

  async function acceptTokens(access: string, refresh: string) {
    setTokens(access, refresh);
    await loadMe();
  }

  function logout() {
    clearTokens();
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ user, loginWithPassword, acceptTokens, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  return useContext(AuthCtx);
}
```

- [ ] **Step 5: Проверка сборки** — `npm run build` без ошибок (страницы появятся в Task 11; неиспользуемые экспорты — норм).

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(frontend): каркас Vite+React+TS+Tailwind, API-клиент с refresh, AuthContext"
```

---

### Task 11: Фронтенд — страницы и маршруты

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/AuthCallbackPage.tsx`, `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/AdminUsersPage.tsx`, `frontend/src/components/RequireAuth.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/main.tsx`
- Test: `frontend/src/pages/LoginPage.test.tsx`

- [ ] **Step 1: Failing test**

`frontend/src/pages/LoginPage.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import LoginPage from "./LoginPage";

describe("LoginPage", () => {
  it("показывает форму входа и кнопку Яндекса", () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Пароль")).toBeInTheDocument();
    expect(screen.getByText("Войти с Яндексом")).toBeInTheDocument();
  });
});
```

Run: `npm run test` → FAIL (LoginPage не существует).

- [ ] **Step 2: Страницы**

`frontend/src/pages/LoginPage.tsx`:
```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { loginWithPassword } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await loginWithPassword(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-stone-200 bg-white p-8">
        <h1 className="font-serif text-2xl text-stone-900">SmetaApp</h1>
        <a
          href="/api/auth/yandex/login"
          className="block w-full rounded bg-stone-900 px-4 py-2 text-center text-white"
        >
          Войти с Яндексом
        </a>
        <div className="text-center text-sm text-stone-400">или по email</div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm text-stone-600">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded border border-stone-300 px-3 py-2"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm text-stone-600">
              Пароль
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded border border-stone-300 px-3 py-2"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            className="w-full rounded border border-stone-900 px-4 py-2 text-stone-900"
          >
            Войти
          </button>
        </form>
      </div>
    </div>
  );
}
```

`frontend/src/pages/AuthCallbackPage.tsx`:
```tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function AuthCallbackPage() {
  const { acceptTokens } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const access = params.get("access_token");
    const refresh = params.get("refresh_token");
    if (access && refresh) {
      void acceptTokens(access, refresh).then(() => navigate("/", { replace: true }));
    } else {
      navigate("/login", { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div className="p-8 text-stone-500">Входим…</div>;
}
```

`frontend/src/pages/HomePage.tsx`:
```tsx
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function HomePage() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-stone-50">
      <header className="flex items-center justify-between border-b border-stone-200 bg-white px-6 py-3">
        <span className="font-serif text-lg text-stone-900">SmetaApp</span>
        <nav className="flex items-center gap-4 text-sm">
          {user?.role === "admin" && (
            <Link to="/admin/users" className="text-stone-600 hover:text-stone-900">
              Пользователи
            </Link>
          )}
          <span className="text-stone-400">{user?.email}</span>
          <button onClick={logout} className="text-stone-600 hover:text-stone-900">
            Выйти
          </button>
        </nav>
      </header>
      <main className="p-8 text-stone-600">
        Каркас готов. Сметы и прайсы появятся в следующих фазах.
      </main>
    </div>
  );
}
```

`frontend/src/pages/AdminUsersPage.tsx`:
```tsx
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { User } from "../auth/AuthContext";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setUsers(await api<User[]>("/admin/users"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function setStatus(id: number, status: "active" | "blocked") {
    await api(`/admin/users/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    });
    await load();
  }

  return (
    <div className="p-8">
      <h1 className="mb-4 font-serif text-xl text-stone-900">Пользователи</h1>
      {error && <p className="text-red-600">{error}</p>}
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-2">Email</th>
            <th>Имя</th>
            <th>Роль</th>
            <th>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b border-stone-200">
              <td className="py-2">{u.email}</td>
              <td>{u.name}</td>
              <td>{u.role}</td>
              <td>{u.status}</td>
              <td className="space-x-2 text-right">
                {u.status !== "active" && (
                  <button
                    onClick={() => void setStatus(u.id, "active")}
                    className="rounded border border-green-700 px-2 py-1 text-green-700"
                  >
                    Одобрить
                  </button>
                )}
                {u.status !== "blocked" && (
                  <button
                    onClick={() => void setStatus(u.id, "blocked")}
                    className="rounded border border-red-700 px-2 py-1 text-red-700"
                  >
                    Заблокировать
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

`frontend/src/components/RequireAuth.tsx`:
```tsx
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth() {
  const { user, logout } = useAuth();
  if (user === undefined) return <div className="p-8 text-stone-500">Загрузка…</div>;
  if (user === null) return <Navigate to="/login" replace />;
  if (user.status !== "active")
    return (
      <div className="flex min-h-screen items-center justify-center bg-stone-50">
        <div className="max-w-md rounded-lg border border-stone-200 bg-white p-8 text-center">
          <h1 className="mb-2 font-serif text-xl text-stone-900">Аккаунт на рассмотрении</h1>
          <p className="text-sm text-stone-600">
            Администратор должен одобрить ваш доступ. Загляните позже.
          </p>
          <button onClick={logout} className="mt-4 text-sm text-stone-500 underline">
            Выйти
          </button>
        </div>
      </div>
    );
  return <Outlet />;
}
```

`frontend/src/App.tsx` — заменить целиком:
```tsx
import { Route, Routes } from "react-router-dom";
import RequireAuth from "./components/RequireAuth";
import AdminUsersPage from "./pages/AdminUsersPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
      </Route>
    </Routes>
  );
}
```

`frontend/src/main.tsx` — заменить целиком:
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
```

Удалить `frontend/src/App.css` и шаблонный контент Vite, если остался.

- [ ] **Step 3: Тест и сборка зелёные**

Run: `npm run test` → PASS; `npm run build` → без ошибок.

- [ ] **Step 4: Ручная проверка против живого бэкенда**

Запустить бэкенд (`backend/`): `.venv\Scripts\python -m uvicorn app.main:app --port 8000` (Postgres из Task 3 должен работать, миграции применены) и фронт (`frontend/`): `npm run dev`. На `http://localhost:5173`: регистрация через curl/Swagger → вход по email → видна главная; второй пользователь видит экран «Аккаунт на рассмотрении»; админ одобряет на `/admin/users`.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(frontend): вход (Яндекс + email), pending-экран, админка пользователей"
```

---

### Task 12: Docker — прод и dev

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`, `frontend/Dockerfile`, `frontend/.dockerignore`, `frontend/Caddyfile`, `docker-compose.yml`, `docker-compose.dev.yml`, `.env.example`

- [ ] **Step 1: Dockerfiles**

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

`backend/.dockerignore`:
```
.venv
__pycache__
.pytest_cache
.ruff_cache
tests
```

`frontend/Dockerfile`:
```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv/www
COPY Caddyfile /etc/caddy/Caddyfile
```

`frontend/.dockerignore`:
```
node_modules
dist
```

`frontend/Caddyfile`:
```
{$SITE_ADDRESS::80} {
	encode gzip

	handle /api/* {
		reverse_proxy backend:8000
	}

	handle {
		root * /srv/www
		try_files {path} /index.html
		file_server
	}
}
```

- [ ] **Step 2: Compose**

`docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: smeta
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-smeta}
      POSTGRES_DB: smeta
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U smeta"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+psycopg://smeta:${POSTGRES_PASSWORD:-smeta}@db:5432/smeta
      SECRET_KEY: ${SECRET_KEY:?SECRET_KEY required}
      YANDEX_CLIENT_ID: ${YANDEX_CLIENT_ID:-}
      YANDEX_CLIENT_SECRET: ${YANDEX_CLIENT_SECRET:-}
      FRONTEND_URL: ${FRONTEND_URL:-http://localhost}
      BACKEND_URL: ${BACKEND_URL:-http://localhost}
    depends_on:
      db:
        condition: service_healthy

  web:
    build: ./frontend
    environment:
      SITE_ADDRESS: ${SITE_ADDRESS:-:80}
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend

volumes:
  pgdata:
```

`docker-compose.dev.yml`:
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: smeta
      POSTGRES_PASSWORD: smeta
      POSTGRES_DB: smeta
    ports:
      - "5432:5432"
    volumes:
      - pgdata_dev:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U smeta"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    command: sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+psycopg://smeta:smeta@db:5432/smeta
    depends_on:
      db:
        condition: service_healthy

  frontend:
    image: node:22-alpine
    working_dir: /app
    command: sh -c "npm install && npm run dev -- --host"
    volumes:
      - ./frontend:/app
    ports:
      - "5173:5173"
    environment:
      VITE_PROXY_TARGET: http://backend:8000

volumes:
  pgdata_dev:
```

`.env.example` (корень):
```
# Прод (docker-compose.yml). Скопировать в .env и заполнить.
SECRET_KEY=
POSTGRES_PASSWORD=
YANDEX_CLIENT_ID=
YANDEX_CLIENT_SECRET=
SITE_ADDRESS=smetaapp.ru
FRONTEND_URL=https://smetaapp.ru
BACKEND_URL=https://smetaapp.ru
```

- [ ] **Step 3: Проверка dev-окружения**

Остановить временный Postgres из Task 3: `docker rm -f smeta-pg-tmp`.
```powershell
docker compose -f docker-compose.dev.yml up -d --build
```
Expected: `http://localhost:5173` открывается, вход работает (миграции применились автоматически). `docker compose -f docker-compose.dev.yml logs backend` без ошибок.

- [ ] **Step 4: Проверка прод-сборки локально**

```powershell
$env:SECRET_KEY='test-secret'; docker compose up -d --build
```
Expected: `http://localhost` отдаёт фронт, `http://localhost/api/health` → `{"status":"ok"}`. После проверки: `docker compose down`.

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore frontend/Dockerfile frontend/.dockerignore frontend/Caddyfile docker-compose.yml docker-compose.dev.yml .env.example
git commit -m "feat(infra): Docker Compose прод (caddy+static) и dev (hot-reload)"
```

---

### Task 13: CI и README

**Files:**
- Create: `.github/workflows/ci.yml`, `README.md`

- [ ] **Step 1: Workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check .
      - run: pytest -q

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run test
      - run: npm run build
```

- [ ] **Step 2: README**

`README.md`:
```markdown
# SmetaApp

Приложение для составления смет и КП на базе прайсов поставщиков.
Дизайн системы: `docs/superpowers/specs/2026-06-11-smeta-app-design.md`.

## Стек

FastAPI + PostgreSQL + React (Vite, Tailwind) + Caddy. Подробности — в спеке.

## Разработка

```powershell
docker compose -f docker-compose.dev.yml up -d --build
# фронт: http://localhost:5173, API: http://localhost:8000/docs
```

Тесты: `cd backend; .venv\Scripts\python -m pytest -q` и `cd frontend; npm run test`.

## Прод

Скопировать `.env.example` → `.env`, заполнить секреты, затем:

```bash
docker compose up -d --build
```

## Яндекс OAuth

Создать приложение на https://oauth.yandex.ru/ (доступ: email, имя),
redirect URI: `<BACKEND_URL>/api/auth/yandex/callback`.
ID/секрет — в `.env` (`YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`).
Первый зарегистрировавшийся пользователь автоматически становится активным админом.
```

- [ ] **Step 3: Финальная проверка фазы**

- `cd backend; .venv\Scripts\python -m pytest -q` — все зелёные
- `.venv\Scripts\ruff check .` — чисто
- `cd frontend; npm run test; npm run build` — зелёные
- `git status` — нет неучтённых файлов

- [ ] **Step 4: Commit**

```bash
git add .github README.md
git commit -m "ci: GitHub Actions (ruff+pytest, vitest+build) + README"
```

- [ ] **Step 5: Обновить graphify-граф** (политика проекта: после каждой фазы)

Вызвать скил `graphify` на `D:\git\smeta_local_app` — обновить общий граф в `D:/git/graphify-out/`.

---

## Что НЕ входит в фазу 1 (не делать)

- Каталог, прайсы, импорт — фаза 2
- Сметы, клиенты, ценовые уровни — фаза 3
- Экспорт, публичные ссылки — фаза 4
- AI — фаза 5; PWA-манифест, деплой на сервер, DNS — фаза 6
- Хранение refresh-токенов в БД с отзывом — осознанно отложено (stateless JWT достаточно для v1)

## Self-review (выполнен при написании плана)

- Покрытие фазы 1 из спеки: структура репо ✓ (Task 1, 9, 10), Docker ✓ (12), alembic ✓ (3), скелеты модулей ✓ (9), CI ✓ (13), Яндекс OAuth ✓ (7), email/пароль ✓ (5), JWT ✓ (4, 6), роли + pending ✓ (5, 6, 8, 11)
- Плейсхолдеров нет: каждый шаг содержит полный код/команды
- Согласованность типов: `issue_tokens` возвращает dict с ключами `access_token/refresh_token/token_type` (Task 5) — используется в Task 7; `UserOut` (Task 5) — в Task 8; фронтовый `User` (Task 10) — в Task 11
