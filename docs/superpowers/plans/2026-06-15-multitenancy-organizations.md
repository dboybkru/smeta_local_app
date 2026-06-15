# Мультиарендность Этап A (Организации) — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Tasks are sequential (shared files: models, migrations chain, deps) — do NOT parallelize.

**Goal:** Добавить «измерение организации» во всё приложение: данные каждой организации изолированы (404 на чужое), иерархия ролей superuser→org_admin→estimator→viewer, онбординг инвайтом по email, миграция текущих данных в дефолтную орг.

**Architecture:** Новая таблица `organizations`; `org_id` на User(nullable)/Estimate/Client/CatalogItem/Supplier/PriceList/PriceLevel/CompanyProfile(NOT NULL, дочерние наследуют). Зависимость `current_org` скоупит каждый запрос; чужая орг → 404. Роли: `User.is_superuser`(флаг) + `role` в {org_admin,estimator,viewer}. Онбординг — предсоздание `User(status="invited")` + claim по email при входе. Одна Alembic-цепочка миграций с backfill в дефолтную орг.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic + pytest (SQLite); React 19 + TS + Vite + Vitest.

**Спек:** `docs/superpowers/specs/2026-06-15-multitenancy-organizations-design.md`

**Команды (Windows, из `backend`):** тесты `./.venv/Scripts/python.exe -m pytest -q`; одиночный `... -m pytest tests/test_x.py -q`; линт `./.venv/Scripts/ruff.exe check app/`. Фронт (из `frontend`): `npm run test`, `npm run build`, `npm run lint`. Текущий head миграций: `e2f3a4b5c6d7`.

**Глобальный инвариант изоляции:** в `app/auth/deps.py` появится `current_org(user) -> int` (см. Task 2). Любой сервис, читающий/пишущий орг-данные, фильтрует по нему. Чужая строка → 404, не 403 (не раскрываем существование).

---

## Структура файлов
- Создать: `backend/app/orgs/__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`.
- Изменить модели: `app/auth/models.py`(User), `app/estimates/models.py`(Client, Estimate), `app/catalog/models.py`(Supplier, PriceList, PriceLevel, CatalogItem), `app/profile/models.py`(CompanyProfile).
- Изменить deps/scoping: `app/auth/deps.py`, `app/auth/router.py`(claim), `app/estimates/service.py`+`router.py`, `app/catalog/service.py`+`router.py`, `app/catalog/importer.py`, `app/catalog/characteristics.py`+`app/jobs/worker.py`(org scope), `app/profile/router.py`, `app/main.py`(подключить orgs router).
- Миграции: по одной на Task 1/2/4/5/6.
- conftest: регистрация `app.orgs.models`.
- Фронт: `src/api/orgs.ts`(new), `src/pages/OrgsPage.tsx`(new), `src/api/admin.ts`/users API, `AppHeader.tsx`, `App.tsx`(route).

---

## Task 1: Организация — модель, миграция, CRUD (суперюзер)

**Files:** Create `backend/app/orgs/__init__.py`, `app/orgs/models.py`, `app/orgs/schemas.py`, `app/orgs/service.py`, `app/orgs/router.py`. Modify `app/auth/models.py`, `app/auth/deps.py`, `app/main.py`, `backend/tests/conftest.py`. Create migration. Test `backend/tests/test_orgs.py`.

- [ ] **Step 1: Failing test** — create `backend/tests/test_orgs.py`:

```python
from app.auth.models import User
from app.core.security import create_access_token


def _user(db, role="org_admin", su=False, status="active"):
    u = User(email=f"{role}{su}@x.ru", name="U", role=role, status=status, is_superuser=su)
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_superuser_creates_and_lists_orgs(client, db_session):
    su = _user(db_session, su=True)
    r = client.post("/api/orgs", json={"name": "Фирма А"}, headers=_hdr(su))
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Фирма А"
    lst = client.get("/api/orgs", headers=_hdr(su)).json()
    assert any(o["name"] == "Фирма А" for o in lst)


def test_duplicate_org_name_409(client, db_session):
    su = _user(db_session, su=True)
    client.post("/api/orgs", json={"name": "Дубль"}, headers=_hdr(su))
    assert client.post("/api/orgs", json={"name": "Дубль"}, headers=_hdr(su)).status_code == 409


def test_non_superuser_cannot_manage_orgs(client, db_session):
    admin = _user(db_session, role="org_admin", su=False)
    assert client.get("/api/orgs", headers=_hdr(admin)).status_code == 403
    assert client.post("/api/orgs", json={"name": "X"}, headers=_hdr(admin)).status_code == 403
```

- [ ] **Step 2: Run → FAIL** `./.venv/Scripts/python.exe -m pytest tests/test_orgs.py -q` → ImportError/404 (no `is_superuser`, no orgs router).

- [ ] **Step 3: Create `app/orgs/__init__.py`** (empty) and `app/orgs/models.py`:

```python
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 4: Add `is_superuser` to User.** In `app/auth/models.py`, change `ROLES = ("admin", "estimator", "viewer")` to `ROLES = ("org_admin", "estimator", "viewer")` and `STATUSES = ("pending", "active", "blocked")` to `STATUSES = ("pending", "active", "blocked", "invited")`. Add to class User (after `status`): import `Boolean` from sqlalchemy (add to the existing `from sqlalchemy import ...` line) and:

```python
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
```

(org_id is added in Task 2.)

- [ ] **Step 5: Add `require_superuser` dep.** In `app/auth/deps.py` append:

```python
def require_superuser(user: User = Depends(require_active)) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Нужны права суперпользователя")
    return user
```

- [ ] **Step 6: Schemas** `app/orgs/schemas.py`:

```python
from pydantic import BaseModel, ConfigDict, Field


class OrgIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_count: int = 0
```

- [ ] **Step 7: Service** `app/orgs/service.py`:

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.orgs.models import Organization


def list_orgs(db: Session) -> list[dict]:
    rows = db.execute(
        select(Organization, func.count(User.id))
        .outerjoin(User, User.org_id == Organization.id)
        .group_by(Organization.id)
        .order_by(Organization.name)
    ).all()
    return [{"id": o.id, "name": o.name, "user_count": n} for o, n in rows]


def create_org(db: Session, name: str) -> Organization:
    org = Organization(name=name)
    db.add(org); db.commit(); db.refresh(org)
    return org


def get_org(db: Session, org_id: int) -> Organization | None:
    return db.get(Organization, org_id)
```

NOTE: `User.org_id` referenced here exists only after Task 2; Task 1 migration adds the column (Step 9) so the model attribute must also exist. To avoid a forward-reference problem, ADD the `org_id` column to the User model NOW in Step 4 as well:
```python
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
```
(import `ForeignKey` in auth/models.py). This is harmless — Task 2 fills logic/migration/backfill around it.

- [ ] **Step 8: Router** `app/orgs/router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import require_superuser
from app.auth.models import User
from app.core.db import get_db
from app.orgs import service
from app.orgs.models import Organization
from app.orgs.schemas import OrgIn, OrgOut

# Гейт НЕ на уровне роутера: org CRUD — суперюзер (per-endpoint), а user-management
# эндпоинты (Task 3) гейтятся require_org_admin. Поэтому каждый эндпоинт объявляет свой гейт.
router = APIRouter(prefix="/api/orgs", tags=["orgs"])


@router.get("", response_model=list[OrgOut])
def list_orgs(db: Session = Depends(get_db), _: User = Depends(require_superuser)):
    return service.list_orgs(db)


@router.post("", response_model=OrgOut, status_code=201)
def create_org(body: OrgIn, db: Session = Depends(get_db), _: User = Depends(require_superuser)):
    if db.scalar(__import__("sqlalchemy").select(Organization).where(Organization.name == body.name)):
        raise HTTPException(status_code=409, detail="Организация с таким именем уже есть")
    org = service.create_org(db, body.name)
    return {"id": org.id, "name": org.name, "user_count": 0}


@router.patch("/{org_id}", response_model=OrgOut)
def rename_org(org_id: int, body: OrgIn, db: Session = Depends(get_db)):
    org = service.get_org(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    if body.name != org.name and db.scalar(
        __import__("sqlalchemy").select(Organization).where(Organization.name == body.name)
    ):
        raise HTTPException(status_code=409, detail="Организация с таким именем уже есть")
    org.name = body.name; db.commit()
    return {"id": org.id, "name": org.name, "user_count": 0}
```

- [ ] **Step 9: Register router + conftest + migration.**
  - `app/main.py`: `from app.orgs.router import router as orgs_router` and `app.include_router(orgs_router)`.
  - `tests/conftest.py`: add `from app.orgs import models as _orgs_models  # noqa: E402, F401` (before `from app.main import app`).
  - Create migration `backend/alembic/versions/f1a2b3c4d5e6_organizations.py`:

```python
"""organizations + user.is_superuser + user.org_id (nullable) + default org

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2026-06-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_organizations_name"),
    )
    # дефолтная организация
    op.execute(
        "INSERT INTO organizations (name, created_at) VALUES ('Организация', now())"
    )
    op.add_column("users", sa.Column(
        "is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column(
        "org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True))
    op.create_index("ix_users_org_id", "users", ["org_id"])
    # все текущие пользователи -> дефолтная орг
    op.execute("UPDATE users SET org_id = (SELECT min(id) FROM organizations)")
    # текущие админы -> суперюзеры + роль org_admin
    op.execute("UPDATE users SET is_superuser = true WHERE role = 'admin'")
    op.execute("UPDATE users SET role = 'org_admin' WHERE role = 'admin'")


def downgrade() -> None:
    op.drop_index("ix_users_org_id", table_name="users")
    op.drop_column("users", "org_id")
    op.drop_column("users", "is_superuser")
    op.drop_table("organizations")
```

- [ ] **Step 10: Run tests** `./.venv/Scripts/python.exe -m pytest tests/test_orgs.py -q` → PASS (3). Full suite may have failures in tests that used `role="admin"` — those are addressed in Task 2/3; run `tests/test_orgs.py` only here. Lint `./.venv/Scripts/ruff.exe check app/orgs app/auth/deps.py` → clean.

- [ ] **Step 11: Commit**
```bash
git add backend/app/orgs backend/app/auth/models.py backend/app/auth/deps.py backend/app/main.py backend/tests/conftest.py backend/tests/test_orgs.py backend/alembic/versions/f1a2b3c4d5e6_organizations.py
git commit -m "feat(orgs): модель Organization, is_superuser, CRUD орг (суперюзер) + миграция"
```

---

## Task 2: current_org + require_org_admin + перевод require_admin

**Files:** Modify `app/auth/deps.py`. Test `backend/tests/test_deps_org.py`.

Goal: единый механизм скоупа и обновлённые гейты ролей. После этой задачи `require_admin` БОЛЬШЕ НЕ опирается на `role=="admin"` (такой роли нет).

- [ ] **Step 1: Failing test** `backend/tests/test_deps_org.py`:

```python
import pytest
from fastapi import HTTPException

from app.auth.deps import current_org, require_org_admin, require_superuser
from app.auth.models import User


def test_current_org_returns_user_org():
    u = User(id=1, org_id=7, role="estimator", status="active")
    assert current_org(u) == 7


def test_current_org_none_raises_403():
    u = User(id=1, org_id=None, role="estimator", status="active")
    with pytest.raises(HTTPException) as e:
        current_org(u)
    assert e.value.status_code == 403


def test_require_org_admin_allows_admin_and_superuser():
    assert require_org_admin(User(id=1, org_id=1, role="org_admin", status="active"))
    assert require_org_admin(User(id=2, org_id=1, role="estimator", status="active", is_superuser=True))


def test_require_org_admin_denies_estimator():
    with pytest.raises(HTTPException) as e:
        require_org_admin(User(id=3, org_id=1, role="estimator", status="active"))
    assert e.value.status_code == 403
```

- [ ] **Step 2: Run → FAIL** (`current_org`/`require_org_admin` not defined).

- [ ] **Step 3: Implement in `app/auth/deps.py`** — append:

```python
def current_org(user: User = Depends(require_active)) -> int:
    if user.org_id is None:
        raise HTTPException(
            status_code=403, detail="Аккаунт не привязан к организации"
        )
    return user.org_id


def require_org_admin(user: User = Depends(require_active)) -> User:
    if not (user.is_superuser or user.role == "org_admin"):
        raise HTTPException(status_code=403, detail="Нужны права администратора организации")
    return user
```
Then REPLACE the body of the existing `require_admin` so callers keep working as org-admin gate:
```python
def require_admin(user: User = Depends(require_active)) -> User:
    if not (user.is_superuser or user.role == "org_admin"):
        raise HTTPException(status_code=403, detail="Нужны права администратора")
    return user
```
(`require_admin` is kept as an alias of org-admin to avoid touching every existing router import; new code uses `require_org_admin`/`require_superuser`. Глобальные суперюзер-операции (AI/настройки) переключим на `require_superuser` в Task 6.)

NOTE: the unit test calls `current_org(u)` with a `User` positionally — that works because `Depends(...)` defaults are ignored on direct calls. Keep the signature with the Depends default (FastAPI needs it for DI).

- [ ] **Step 4: Run** `./.venv/Scripts/python.exe -m pytest tests/test_deps_org.py -q` → PASS. Lint clean.

- [ ] **Step 5: Commit**
```bash
git add backend/app/auth/deps.py backend/tests/test_deps_org.py
git commit -m "feat(auth): current_org + require_org_admin/superuser; require_admin = org-admin"
```

---

## Task 3: Онбординг — инвайт + claim по email + управление пользователями орг

**Files:** Modify `app/auth/service.py` (claim helpers), `app/auth/router.py` (register/yandex claim), `app/auth/admin_router.py` (org-scoped user mgmt + invite). Test `backend/tests/test_onboarding.py`. Also fix existing auth/admin tests that assumed `role="admin"` (rename to `org_admin`/`is_superuser`).

- [ ] **Step 1: Failing test** `backend/tests/test_onboarding.py`:

```python
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
    u = db_session.scalars(__import__("sqlalchemy").select(User).where(User.email == "new@x.ru")).one()
    assert u.status == "invited" and u.org_id == o.id and u.role == "estimator"


def test_register_claims_invited(client, db_session):
    su, o = _su(db_session)
    client.post(f"/api/orgs/{o.id}/users", json={"email": "claim@x.ru", "role": "estimator"},
                headers=_hdr(su))
    r = client.post("/api/auth/register", json={"email": "claim@x.ru", "password": "Pass12345",
                                                "name": "Claimed"})
    assert r.status_code in (200, 201), r.text
    u = db_session.scalars(__import__("sqlalchemy").select(User).where(User.email == "claim@x.ru")).one()
    assert u.status == "active" and u.org_id == o.id and u.password_hash


def test_self_register_without_invite_is_pending_orgless(client, db_session):
    # вторая регистрация (не первый юзер): pending без орг
    _su(db_session)  # система уже не пустая
    r = client.post("/api/auth/register", json={"email": "self@x.ru", "password": "Pass12345",
                                                "name": "Self"})
    assert r.status_code in (200, 201)
    u = db_session.scalars(__import__("sqlalchemy").select(User).where(User.email == "self@x.ru")).one()
    assert u.status == "pending" and u.org_id is None
```

- [ ] **Step 2: Run → FAIL** (no invite endpoint; register doesn't claim).

- [ ] **Step 3: Invite endpoint** in `app/auth/admin_router.py`. Read the file first. Add (using `require_org_admin` + ensuring the target org matches caller unless superuser):

```python
from app.auth.deps import require_org_admin, require_superuser  # add to imports
from app.orgs.models import Organization  # add

@router.post("/orgs/{org_id}/users", status_code=201)
def invite_user(org_id: int, body: dict, db: Session = Depends(get_db),
                actor: User = Depends(require_org_admin)):
    if not actor.is_superuser and actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="Чужая организация")
    if db.get(Organization, org_id) is None:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    email = (body.get("email") or "").strip().lower()
    role = body.get("role") or "estimator"
    if not email or role not in ("org_admin", "estimator", "viewer"):
        raise HTTPException(status_code=422, detail="email и валидная роль обязательны")
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже есть")
    u = User(email=email, role=role, status="invited", org_id=org_id, name="")
    db.add(u); db.commit(); db.refresh(u)
    return {"id": u.id, "email": u.email, "role": u.role, "status": u.status}
```
(Place under the existing `router` in admin_router.py. The admin_router prefix is likely `/api/admin` or similar — VERIFY its prefix; the test calls `/api/orgs/{id}/users`. If admin_router prefix differs, instead register this route in `app/orgs/router.py` which already has prefix `/api/orgs` and `require_superuser`. PREFERRED: put invite + list/patch user endpoints in `orgs/router.py` but relax its blanket `require_superuser` so org_admins can manage their own org. Implementation: remove the router-level `dependencies=[require_superuser]` from orgs/router (Task 1), keep `require_superuser` on org create/rename/list per-endpoint, and add user-management endpoints gated by `require_org_admin` with the same-org check. Apply THIS approach — adjust Task 1's router accordingly when you reach it, or refactor here.)

- [ ] **Step 4: List/patch org users** in `app/orgs/router.py` (org_admin own org / superuser any):

```python
@router.get("/{org_id}/users")
def list_org_users(org_id: int, db: Session = Depends(get_db),
                   actor: User = Depends(require_org_admin)):
    if not actor.is_superuser and actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="Чужая организация")
    rows = db.scalars(select(User).where(User.org_id == org_id).order_by(User.email)).all()
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role,
             "status": u.status} for u in rows]


@router.patch("/{org_id}/users/{uid}")
def update_org_user(org_id: int, uid: int, body: dict, db: Session = Depends(get_db),
                    actor: User = Depends(require_org_admin)):
    if not actor.is_superuser and actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="Чужая организация")
    u = db.get(User, uid)
    if u is None or u.org_id != org_id:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if (role := body.get("role")) in ("org_admin", "estimator", "viewer"):
        u.role = role
    if (status := body.get("status")) in ("active", "blocked"):
        u.status = status
    db.commit()
    return {"id": u.id, "email": u.email, "role": u.role, "status": u.status}
```
(Imports needed in orgs/router.py: `from app.auth.deps import require_org_admin`, `from app.auth.models import User`, `from sqlalchemy import select`.)

- [ ] **Step 5: Claim logic in register.** Read `app/auth/service.py` + `register` in `app/auth/router.py`. Modify registration so that if an `invited` user with that email exists (no password), it is claimed: set password_hash, name, status="active" (keep org_id/role). Otherwise create as today, BUT non-first users default to `status="pending", org_id=None`. Pseudocode of the register service change:

```python
def register_user(db, email, password, name):
    email = email.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        if existing.status == "invited" and not existing.password_hash:
            existing.password_hash = hash_password(password)
            existing.name = name or existing.name
            existing.status = "active"
            db.commit(); db.refresh(existing)
            return existing
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")
    first = db.scalar(select(func.count(User.id))) == 0
    user = User(
        email=email, password_hash=hash_password(password), name=name,
        role="org_admin" if first else "estimator",
        status="active" if first else "pending",
        is_superuser=first,
        org_id=None,
    )
    db.add(user); db.commit(); db.refresh(user)
    return user
```
Adapt to the actual existing function names/signatures in `auth/service.py` (keep its hashing helper). Keep the "first user = superuser/active" behavior.

- [ ] **Step 6: Claim logic in Yandex callback.** In `app/auth/router.py` yandex callback (after `fetch_userinfo` gives email): if an `invited` user with that email exists, set `yandex_id`, `name`, `status="active"`, keep org/role; else existing-by-email login; else create `status="pending", org_id=None`. Mirror the register claim. Read the callback and adapt.

- [ ] **Step 7: Fix pre-existing auth tests** that used `role="admin"`: grep `role="admin"` / `role='admin'` across `backend/tests` and replace with `role="org_admin"` + add `is_superuser=True` where the test expects superuser/global-admin powers (e.g. AI config, settings). Run the auth/admin test files to confirm green.

- [ ] **Step 8: Run** `./.venv/Scripts/python.exe -m pytest tests/test_onboarding.py tests/test_auth*.py tests/test_orgs.py -q` → PASS. Lint clean.

- [ ] **Step 9: Commit**
```bash
git add backend/app/auth backend/app/orgs/router.py backend/tests/test_onboarding.py
git commit -m "feat(auth): инвайт по email + claim (register/yandex) + управление пользователями орг"
```

---

## Task 4: Изоляция смет и клиентов

**Files:** Modify `app/estimates/models.py`(Client, Estimate +org_id), `app/estimates/service.py`(scope), `app/estimates/router.py`(pass org). Migration. Test `backend/tests/test_estimate_isolation.py`.

- [ ] **Step 1: Failing test** `backend/tests/test_estimate_isolation.py`:

```python
from app.auth.models import User
from app.core.security import create_access_token
from app.estimates import models as em
from app.orgs.models import Organization


def _org_user(db, name):
    o = Organization(name=name); db.add(o); db.commit()
    u = User(email=f"a{name}@x.ru", name="A", role="org_admin", status="active", org_id=o.id)
    db.add(u); db.commit(); return o, u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_estimate_not_visible_across_orgs(client, db_session):
    oa, ua = _org_user(db_session, "A"); ob, ub = _org_user(db_session, "B")
    est = em.Estimate(owner_id=ua.id, org_id=oa.id, object_name="Секрет A")
    db_session.add(est); db_session.commit()
    # B не видит смету A
    assert client.get(f"/api/estimates/{est.id}", headers=_hdr(ub)).status_code == 404
    # B не видит её в списке
    lst = client.get("/api/estimates", headers=_hdr(ub)).json()
    assert all(e["id"] != est.id for e in (lst if isinstance(lst, list) else lst.get("items", [])))
    # A видит
    assert client.get(f"/api/estimates/{est.id}", headers=_hdr(ua)).status_code == 200


def test_client_isolated_across_orgs(client, db_session):
    oa, ua = _org_user(db_session, "CA"); ob, ub = _org_user(db_session, "CB")
    db_session.add(em.Client(name="Клиент A", org_id=oa.id)); db_session.commit()
    lst = client.get("/api/clients", headers=_hdr(ub)).json()
    assert all(c["name"] != "Клиент A" for c in lst)
```

- [ ] **Step 2: Run → FAIL** (no org_id; lists not scoped).

- [ ] **Step 3: Add org_id to models.** In `app/estimates/models.py`: import `ForeignKey` (already imported). Add to `Client`: `org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)`. Add to `Estimate`: same. (NOT NULL enforced by migration; model attr no `| None`.)

- [ ] **Step 4: Scope service.** In `app/estimates/service.py`:
  - `get_owned_estimate(db, estimate_id, user)`: after fetching `est`, FIRST `if est.org_id != user.org_id: raise 404` (before the owner check). 
  - `list_estimates`/the function backing `GET /api/estimates`: add `.where(Estimate.org_id == user.org_id)`; estimator also `.where(owner_id == user.id)`.
  - Client list/get/create: scope by org — list `.where(Client.org_id == org)`; create sets `org_id=org`; get → 404 if other org.
  Read the file and apply to every Estimate/Client query. Creation paths (`create_estimate`, client create) set `org_id = user.org_id`.

- [ ] **Step 5: Router passes org.** In `app/estimates/router.py`, every endpoint already has `user`; ensure service calls receive user/org so scoping applies. For client create endpoints set `org_id=current_org`. Add `Depends(current_org)` where a raw org int is convenient. Read and wire.

- [ ] **Step 6: Migration** `backend/alembic/versions/a2b3c4d5e6f7_estimates_clients_org.py` (down_revision `f1a2b3c4d5e6`): add nullable `org_id` to `clients` and `estimates`, backfill `= (SELECT min(id) FROM organizations)`, set NOT NULL, add FK+index. Pattern:

```python
def upgrade() -> None:
    for t in ("clients", "estimates"):
        op.add_column(t, sa.Column("org_id", sa.Integer(), nullable=True))
        op.execute(f"UPDATE {t} SET org_id = (SELECT min(id) FROM organizations)")
        op.alter_column(t, "org_id", nullable=False)
        op.create_foreign_key(f"fk_{t}_org", t, "organizations", ["org_id"], ["id"])
        op.create_index(f"ix_{t}_org_id", t, ["org_id"])

def downgrade() -> None:
    for t in ("estimates", "clients"):
        op.drop_index(f"ix_{t}_org_id", table_name=t)
        op.drop_constraint(f"fk_{t}_org", t, type_="foreignkey")
        op.drop_column(t, "org_id")
```
(Full revision boilerplate as in Task 1.)

- [ ] **Step 7: Run** `./.venv/Scripts/python.exe -m pytest tests/test_estimate_isolation.py tests/test_estimates*.py tests/test_lines*.py tests/test_clients*.py -q` → PASS. Fix any existing estimate/client test that now needs `org_id` on created rows (add `org_id=<org>` in fixtures). Lint clean.

- [ ] **Step 8: Commit**
```bash
git add backend/app/estimates backend/alembic/versions/a2b3c4d5e6f7_estimates_clients_org.py backend/tests/test_estimate_isolation.py
git commit -m "feat(estimates): org_id + изоляция смет и клиентов по организации"
```

---

## Task 5: Изоляция каталога (товары, поставщики, прайсы, уровни) + уникальности + extract-job

**Files:** Modify `app/catalog/models.py`(Supplier, PriceList, PriceLevel, CatalogItem +org_id; уникальности), `app/catalog/service.py`(search/facets/prices scope), `app/catalog/router.py`(suppliers/price-levels/import/items/facets/price-lists/extract scope), `app/catalog/importer.py`(set org_id), `app/catalog/characteristics.py` + `app/jobs/worker.py`(org scope). Migration. Test `backend/tests/test_catalog_isolation.py`.

- [ ] **Step 1: Failing test** `backend/tests/test_catalog_isolation.py`:

```python
from app.auth.models import User
from app.catalog.models import CatalogItem, PriceLevel, Supplier
from app.core.security import create_access_token
from app.orgs.models import Organization


def _org_admin(db, name):
    o = Organization(name=name); db.add(o); db.commit()
    u = User(email=f"c{name}@x.ru", name="A", role="org_admin", status="active", org_id=o.id)
    db.add(u); db.commit(); return o, u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_catalog_items_isolated(client, db_session):
    oa, ua = _org_admin(db_session, "KA"); ob, ub = _org_admin(db_session, "KB")
    sup = Supplier(name="S", org_id=oa.id); db_session.add(sup); db_session.commit()
    db_session.add(CatalogItem(supplier_id=sup.id, org_id=oa.id, name="Камера A", kind="material"))
    db_session.commit()
    items = client.get("/api/catalog/items", headers=_hdr(ub)).json()["items"]
    assert all(i["name"] != "Камера A" for i in items)
    items_a = client.get("/api/catalog/items", headers=_hdr(ua)).json()["items"]
    assert any(i["name"] == "Камера A" for i in items_a)


def test_same_price_level_name_allowed_in_two_orgs(db_session):
    oa, _ = _org_admin(db_session, "PA"); ob, _ = _org_admin(db_session, "PB")
    db_session.add(PriceLevel(name="Розница", org_id=oa.id))
    db_session.add(PriceLevel(name="Розница", org_id=ob.id))
    db_session.commit()  # must NOT raise (per-org unique)
```

- [ ] **Step 2: Run → FAIL** (no org_id; global unique on PriceLevel.name raises on duplicate).

- [ ] **Step 3: Models.** In `app/catalog/models.py` add `org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)` to `Supplier`, `PriceList`, `PriceLevel`, `CatalogItem`. Change `PriceLevel.name` from `unique=True` to plain `String(100)` and add `__table_args__ = (UniqueConstraint("org_id", "name"),)`. Change `Supplier.name` from `unique=True` to plain + `__table_args__ = (UniqueConstraint("org_id", "name"),)`. (CatalogItem keeps its existing UC; ItemPrice unchanged.)

- [ ] **Step 4: Scope service.** In `app/catalog/service.py`: `search_items(db, ..., org_id: int)` — add param and `.where(CatalogItem.org_id == org_id)`; `latest_prices_for` is by item_ids (already scoped via items). In `app/catalog/router.py` pass `org=Depends(current_org)` to: `list_items`, `catalog_facets` (filter `CatalogItem.org_id == org`), `list_suppliers`/`create_supplier` (scope + set org_id, uniqueness check within org), `list_price_levels`/`create/patch/delete_price_level` (scope + set org_id), `list_price_lists`, `item_price_history` (404 if item other org), import (`import_file` → pass org to importer). Read router and apply to EVERY endpoint.

- [ ] **Step 5: Importer sets org.** `app/catalog/importer.py`: `import_parsed(db, supplier_id, ..., org_id)` — set `org_id=org_id` on created `CatalogItem`; `Supplier`/`PriceList`/`PriceLevel` creation paths set org_id. `inspect`/`import` router resolves `org = current_org` and passes through. `_find_item`/`_latest_prices` add `.where(... .org_id == org_id)`.

- [ ] **Step 6: Extract-job org scope.** `app/catalog/characteristics.py`: `extract_batch(db, batch, supplier_id, org_id)` adds `.where(CatalogItem.org_id == org_id)`. `app/catalog/router.py` `start_extract_characteristics` puts `org_id` (current_org) into `Job.params`. `app/jobs/worker.py` `_run_catalog_extract` reads `org_id = (job.params or {}).get("org_id")` and passes to `extract_batch` + `_remaining`.

- [ ] **Step 7: Migration** `backend/alembic/versions/b3c4d5e6f7a8_catalog_org.py` (down_revision `a2b3c4d5e6f7`): add nullable org_id to suppliers/price_lists/price_levels/catalog_items, backfill min org, NOT NULL, FK+index; DROP global unique on `suppliers.name` and `price_levels.name`, CREATE unique `(org_id,name)` for each. Pattern as Task 4 plus:
```python
    op.drop_constraint("uq_price_levels_name", "price_levels", type_="unique")  # имя констрейнта уточнить
    op.create_unique_constraint("uq_price_levels_org_name", "price_levels", ["org_id", "name"])
    op.drop_constraint("uq_suppliers_name", "suppliers", type_="unique")
    op.create_unique_constraint("uq_suppliers_org_name", "suppliers", ["org_id", "name"])
```
VERIFY actual existing unique-constraint names via `\d price_levels` logic or by inspecting the original create migrations (`4b72ceb2e512_*`); SQLite (tests) recreates from models so constraint-drop matters only on Postgres — use `batch_alter_table` if needed for SQLite compatibility, or guard drops with try/except on dialect. SIMPLEST cross-db: since tests use `create_all` from models (not migrations), the unique-constraint drop only must work on Postgres; write it for Postgres and note SQLite tests rely on models.

- [ ] **Step 8: Run** `./.venv/Scripts/python.exe -m pytest tests/test_catalog_isolation.py tests/test_catalog*.py tests/test_import*.py tests/test_clear_catalog.py tests/test_parse_rows.py tests/test_characteristics_import.py -q` → PASS. Fix existing catalog tests to set `org_id` on created rows + pass org through. Lint clean.

- [ ] **Step 9: Commit**
```bash
git add backend/app/catalog backend/app/jobs/worker.py backend/alembic/versions/b3c4d5e6f7a8_catalog_org.py backend/tests/test_catalog_isolation.py
git commit -m "feat(catalog): org_id + изоляция каталога/прайсов + per-org уникальности + extract-job scope"
```

---

## Task 6: CompanyProfile на организацию + перевод глобальных настроек на require_superuser

**Files:** Modify `app/profile/models.py`(CompanyProfile org_id, drop per-user), `app/profile/router.py`(org profile), `app/export/context.py`(profile by org), `app/ai/router.py` + `app/settings/router.py` (require_superuser for global config). Migration. Test `backend/tests/test_profile_org.py`.

- [ ] **Step 1: Failing test** `backend/tests/test_profile_org.py`:

```python
from app.auth.models import User
from app.core.security import create_access_token
from app.orgs.models import Organization


def _org_admin(db, name):
    o = Organization(name=name); db.add(o); db.commit()
    u = User(email=f"p{name}@x.ru", name="A", role="org_admin", status="active", org_id=o.id)
    db.add(u); db.commit(); return o, u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_profile_is_per_org(client, db_session):
    oa, ua = _org_admin(db_session, "PRA"); ob, ub = _org_admin(db_session, "PRB")
    client.put("/api/profile", json={"company_name": "Фирма А"}, headers=_hdr(ua))
    # B видит свой (пустой/свой), не А
    assert client.get("/api/profile", headers=_hdr(ub)).json().get("company_name") != "Фирма А"
    assert client.get("/api/profile", headers=_hdr(ua)).json().get("company_name") == "Фирма А"


def test_ai_config_requires_superuser(client, db_session):
    oa, ua = _org_admin(db_session, "AIA")  # org_admin, NOT superuser
    assert client.get("/api/ai/providers", headers=_hdr(ua)).status_code == 403
```

- [ ] **Step 2: Run → FAIL** (profile per-user; AI providers allowed to org_admin via require_admin alias).

- [ ] **Step 3: CompanyProfile per-org.** Read `app/profile/models.py`. Replace the per-user key (`owner_id`/`user_id` unique) with `org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)`. In `app/profile/router.py` GET/PUT: resolve `org = current_org`; fetch/create the single CompanyProfile for that org (upsert by org_id); only `require_org_admin` may PUT, any active may GET. Read & adapt the existing field set (`company_name`, requisites, etc.) unchanged.

- [ ] **Step 4: Export uses org profile.** In `app/export/context.py` (and any place loading CompanyProfile), load profile by the estimate's `org_id` instead of by user. Read & adapt.

- [ ] **Step 5: Global config → superuser.** In `app/ai/router.py` and `app/settings/router.py`, change the router/endpoint guards from `require_admin` to `require_superuser` (AI providers/models/purposes/usage, DaData, Yandex settings are global infra). Read both routers; replace the dependency import/usage.

- [ ] **Step 6: Migration** `backend/alembic/versions/c4d5e6f7a8b9_profile_org.py` (down_revision `b3c4d5e6f7a8`): add nullable `org_id` to `company_profiles`; backfill: set each existing row's org_id from its owner's org (`UPDATE company_profiles SET org_id = (SELECT org_id FROM users WHERE users.id = company_profiles.owner_id)`); if multiple rows per org, keep the lowest id per org (delete dups: `DELETE FROM company_profiles a USING company_profiles b WHERE a.org_id=b.org_id AND a.id>b.id`); drop old per-user unique/owner column if present; set org_id NOT NULL + unique + FK. VERIFY the actual current PK/owner column name from `app/profile/models.py` before writing the drop. Boilerplate as Task 1.

- [ ] **Step 7: Run** `./.venv/Scripts/python.exe -m pytest tests/test_profile_org.py tests/test_profile*.py tests/test_export*.py tests/test_ai*.py tests/test_settings*.py -q` → PASS. Fix existing profile/ai/settings tests: AI/settings tests now need a superuser actor (`is_superuser=True`); profile tests need org. Lint clean.

- [ ] **Step 8: Commit**
```bash
git add backend/app/profile backend/app/export/context.py backend/app/ai/router.py backend/app/settings/router.py backend/alembic/versions/c4d5e6f7a8b9_profile_org.py backend/tests/test_profile_org.py
git commit -m "feat: CompanyProfile на организацию; глобальные настройки (AI/DaData/Яндекс) под require_superuser"
```

---

## Task 7: Полный бэкенд-прогон + проверка цепочки миграций

**Files:** none (verification + fixups).

- [ ] **Step 1: Full suite** `./.venv/Scripts/python.exe -m pytest -q`. Fix ALL remaining failing tests caused by the new `org_id`/role model (add `org_id`/`is_superuser` in fixtures, replace `role="admin"`). Iterate until green.
- [ ] **Step 2: Lint** `./.venv/Scripts/ruff.exe check app/` → clean.
- [ ] **Step 3: Migration chain linear** — confirm single head: grep `revision`/`down_revision` in `alembic/versions`; chain must be `e2f3a4b5c6d7 → f1a2b3c4d5e6 → a2b3c4d5e6f7 → b3c4d5e6f7a8 → c4d5e6f7a8b9` (head). No branches.
- [ ] **Step 4: Commit** any test fixups:
```bash
git add backend/tests
git commit -m "test: привести существующие тесты к орг-модели (org_id, is_superuser, роли)"
```

---

## Task 8: Фронтенд — организации, инвайт, орг в шапке

**Files:** Create `frontend/src/api/orgs.ts`, `frontend/src/pages/OrgsPage.tsx`. Modify `frontend/src/api/*` (auth/me to expose org+is_superuser), `frontend/src/auth/AuthContext.tsx`, `frontend/src/components/AppHeader.tsx`, `frontend/src/App.tsx`. Tests for new pieces.

- [ ] **Step 1: Expose org/superuser in /me.** Backend: ensure `GET /api/auth/me` returns `org_id`, `org_name`, `is_superuser`, `role`. Read `app/auth/router.py` me endpoint + its schema; add fields (join Organization for name). Add a backend test. (Small backend addition needed for the frontend.)
- [ ] **Step 2: api/orgs.ts** — typed helpers: `listOrgs()`, `createOrg(name)`, `renameOrg(id,name)`, `listOrgUsers(orgId)`, `inviteUser(orgId,{email,role})`, `updateOrgUser(orgId,uid,{role?,status?})` over `api()`. Test in `orgs.test.ts` (mirror existing api tests).
- [ ] **Step 3: OrgsPage.tsx** (`/admin/orgs`, superuser only) — list orgs + create; select an org → manage its users (invite by email+role, change role, block). Mirror existing admin pages styling. Add a smoke test.
- [ ] **Step 4: Header + AuthContext** — `AuthContext` stores `org_name`/`is_superuser`/`role` from /me; `AppHeader` shows org name; «Организации» link visible only if `is_superuser`. «Пользователи» link visible to org_admin (manages own org via the same users UI scoped to `me.org_id`).
- [ ] **Step 5: Route** in `App.tsx`: `/admin/orgs` under RequireAuth.
- [ ] **Step 6: Verify** `npm run test` green, `npm run build` ok, `npm run lint` 0 errors. Backend `pytest -q` still green (me change).
- [ ] **Step 7: Commit**
```bash
git add frontend/src backend/app/auth backend/tests
git commit -m "feat(ui): организации (суперюзер), инвайт по email, орг в шапке + /me org/superuser"
```

---

## Финальная проверка (после всех задач)
- [ ] Бэкенд `pytest -q` + `ruff check app/` зелёные; фронт `npm run test`/`build`/`lint` зелёные.
- [ ] Холистическое ревью свежим субагентом (фокус: НЕТ утечек между орг — каждый список/гет скоупится; claim корректен; миграции на Postgres).
- [ ] ⚠️ **Деплой:** миграции (5 шт) на боевом Postgres — проверить backfill (все строки получили `org_id`, дефолтная орг создана, `daniil.gurov` стал `is_superuser`). FF-merge, redeploy, health 200 (smetaapp + v-s-b.ru). Обновить память.
