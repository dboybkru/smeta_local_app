# Фаза 4a — Бэкенд: экспорт, КП и публичные ссылки — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить каждую смету в коммерческое предложение (КП) с AI-генерацией текстов, экспортом в Excel/PDF и публичными ссылками с тремя уровнями вывода (`full`/`cover`/`estimate`), без раскрытия закупки/маржи в публичном выводе.

**Architecture:** Четыре новых модуля поверх существующего `app.estimates`: `app.profile` (реквизиты исполнителя), `app.proposals` (AI-генерация блоков КП в `Estimate.proposal` JSONB), `app.export` (один Jinja2-шаблон → публичная HTML-страница + PDF через weasyprint; Excel — отдельный openpyxl-генератор), `app.publiclinks` (модель ссылок + админ-CRUD + публичный роутер `/p/{token}` без auth). Claude вызывается через официальный SDK `anthropic` (модель `claude-opus-4-8`), в тестах замокан через единственный seam `_call_claude`. Деньги — Decimal; миграции пишутся вручную и проверяются на Postgres (boolean `server_default` = `'false'`, не `'0'` — урок фазы 3a).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (Mapped/mapped_column), Pydantic v2, Alembic, pytest, openpyxl, weasyprint, Jinja2, anthropic SDK, Postgres (dev :5433) / SQLite (тесты).

---

## File Structure

| Файл | Ответственность |
|---|---|
| `backend/requirements.txt` | + `weasyprint`, `anthropic`, `jinja2` |
| `backend/Dockerfile` | + системные библиотеки weasyprint (pango/cairo/gdk-pixbuf) |
| `backend/app/core/config.py` | + `anthropic_api_key: str = ""` |
| `backend/app/core/types.py` | **Create.** `JSONType` = generic JSON с вариантом JSONB на Postgres |
| `backend/app/profile/__init__.py` | **Create.** пустой |
| `backend/app/profile/models.py` | **Create.** `CompanyProfile` (один на пользователя) |
| `backend/app/profile/schemas.py` | **Create.** `ProfileIn` / `ProfileOut` |
| `backend/app/profile/service.py` | **Create.** `get_or_create_profile`, `upsert_profile` |
| `backend/app/profile/router.py` | **Create.** `GET/PUT /api/profile` |
| `backend/app/estimates/models.py` | **Modify.** + `Estimate.proposal` JSONB nullable |
| `backend/app/proposals/__init__.py` | **Create.** пустой |
| `backend/app/proposals/schemas.py` | **Create.** `ProposalBlocks`, `ProposalPatch` |
| `backend/app/proposals/service.py` | **Create.** `build_prompt`, `_call_claude`, `generate_proposal`, `ProposalAINotConfigured` |
| `backend/app/proposals/router.py` | **Create.** `POST /api/estimates/{id}/proposal/generate`, `PATCH /api/estimates/{id}/proposal` |
| `backend/app/export/__init__.py` | **Create.** пустой |
| `backend/app/export/context.py` | **Create.** `build_export_context(est, *, level, public)` — режет закупку/маржу для public |
| `backend/app/export/excel.py` | **Create.** `render_xlsx(context) -> bytes` |
| `backend/app/export/render.py` | **Create.** `render_html(context, *, watermark)`, `html_to_pdf(html) -> bytes` |
| `backend/app/export/templates/proposal.html` | **Create.** Jinja2-шаблон КП по уровню |
| `backend/app/export/router.py` | **Create.** `GET /api/estimates/{id}/export.xlsx|.pdf?level=` |
| `backend/app/publiclinks/__init__.py` | **Create.** пустой |
| `backend/app/publiclinks/models.py` | **Create.** `PublicLink` |
| `backend/app/publiclinks/schemas.py` | **Create.** `PublicLinkIn` / `PublicLinkOut` |
| `backend/app/publiclinks/service.py` | **Create.** `create_link`, `list_links`, `revoke_link`, `resolve_token` (404/410) |
| `backend/app/publiclinks/router.py` | **Create.** админ-CRUD под auth |
| `backend/app/publiclinks/public_router.py` | **Create.** `GET /p/{token}`, `/p/{token}/pdf` без auth |
| `backend/app/main.py` | **Modify.** include новых роутеров |
| `backend/tests/conftest.py` | **Modify.** import новых моделей для `create_all` |
| migrations × 3 | **Create.** company_profiles; estimates.proposal; public_links |
| tests × ~8 | **Create.** профиль, proposal, excel, render, export, публичные ссылки |

---

## Соглашения (важно для каждой задачи)

- **Auth:** `from app.auth.deps import require_active` → `user: User = Depends(require_active)`. Роли: `admin` видит все сметы, `estimator` — свои, `viewer` — без записи.
- **Владение сметой:** `service.get_owned_estimate(db, estimate_id, user)` (404 если чужая/нет), `service.require_write(est, user)`.
- **БД:** `from app.core.db import get_db, Base`.
- **Тесты:** SQLite in-memory (conftest). Хелперы в каждом тест-файле:
  ```python
  from app.auth.models import User
  from app.core.security import create_access_token

  def _user(db_session, role="estimator", email=None):
      u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active")
      db_session.add(u)
      db_session.commit()
      return u

  def _hdr(u):
      return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}
  ```
- **Регистрация новых моделей:** любая новая таблица должна быть импортирована в `conftest.py`, иначе `Base.metadata.create_all` её не создаст и тесты упадут на «no such table».
- **Деньги:** Decimal; в JSON-ответах сериализуются как строки (Pydantic). В Excel — числом.
- **Команды запуска тестов:** из `backend/` запускать `python -m pytest tests/<файл> -v`. Линт: `python -m ruff check app tests` (если настроен).

---

## Task 1: Зависимости, конфиг, тип JSON

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/core/types.py`
- Modify: `backend/tests/test_config.py`

- [ ] **Step 1: Написать падающий тест на новую настройку**

В `backend/tests/test_config.py` добавить в конец:

```python
def test_anthropic_api_key_defaults_empty():
    from app.core.config import Settings

    s = Settings(_env_file=None)
    assert s.anthropic_api_key == ""
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_config.py::test_anthropic_api_key_defaults_empty -v`
Expected: FAIL (`AttributeError`/`assert` — поля ещё нет).

- [ ] **Step 3: Добавить настройку в конфиг**

В `backend/app/core/config.py` после `backend_url`:

```python
    backend_url: str = "http://localhost:8000"
    anthropic_api_key: str = ""
```

- [ ] **Step 4: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Создать кросс-диалектный тип JSON**

Create `backend/app/core/types.py`:

```python
"""Тип JSON, дающий JSONB на Postgres и обычный JSON на SQLite (тесты)."""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Использовать в mapped_column для JSONB-полей: contacts, utp, cases, proposal.
JSONType = JSON().with_variant(JSONB(), "postgresql")
```

- [ ] **Step 6: Добавить зависимости**

В `backend/requirements.txt` добавить в конец:

```
weasyprint>=62
anthropic>=0.40
jinja2>=3.1
```

- [ ] **Step 7: Добавить системные библиотеки weasyprint в Dockerfile**

Заменить `backend/Dockerfile` целиком на:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
# Системные библиотеки для weasyprint (рендер PDF): pango, cairo, gdk-pixbuf, шрифты.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
        libffi-dev fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 8: Установить новые зависимости в локальное окружение**

Run: `python -m pip install -r requirements.txt`
Expected: `anthropic`, `jinja2` ставятся. `weasyprint` может не поставиться на Windows без GTK — это ОК: PDF-тесты используют `importorskip` и пропускаются локально, реальный рендер проверяется в Docker (Task 8).

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/Dockerfile backend/app/core/config.py backend/app/core/types.py backend/tests/test_config.py
git commit -m "feat(phase4a): deps (weasyprint/anthropic/jinja2), ANTHROPIC_API_KEY, JSONType"
```

---

## Task 2: Модель CompanyProfile + миграция

**Files:**
- Create: `backend/app/profile/__init__.py` (пустой)
- Create: `backend/app/profile/models.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_profile_model.py`
- Create: `backend/alembic/versions/a1b2c3d4e5f6_company_profiles.py`

- [ ] **Step 1: Написать падающий тест модели**

Create `backend/tests/test_profile_model.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.profile.models import CompanyProfile


def _user(db_session, email="u@x.ru"):
    u = User(email=email, name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    return u


def test_profile_defaults(db_session):
    u = _user(db_session)
    p = CompanyProfile(user_id=u.id, org_name="ООО Ромашка")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    assert p.org_name == "ООО Ромашка"
    assert p.contacts == {}
    assert p.utp == []
    assert p.cases == []
    assert p.inn == ""


def test_profile_unique_per_user(db_session):
    u = _user(db_session)
    db_session.add(CompanyProfile(user_id=u.id))
    db_session.commit()
    db_session.add(CompanyProfile(user_id=u.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Зарегистрировать модель в conftest**

В `backend/tests/conftest.py` после строки импорта моделей estimates добавить:

```python
from app.estimates import models as _estimate_models  # noqa: F401
from app.profile import models as _profile_models  # noqa: F401
```

- [ ] **Step 3: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_profile_model.py -v`
Expected: FAIL (`ModuleNotFoundError: app.profile`).

- [ ] **Step 4: Создать модель**

Create `backend/app/profile/__init__.py` (пустой файл).

Create `backend/app/profile/models.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import JSONType


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    org_name: Mapped[str] = mapped_column(String(500), default="")
    inn: Mapped[str] = mapped_column(String(20), default="")
    # contacts: {"phone","email","address","site"}
    contacts: Mapped[dict] = mapped_column(JSONType, default=dict)
    bank_requisites: Mapped[str] = mapped_column(Text, default="")
    utp: Mapped[list] = mapped_column(JSONType, default=list)
    cases: Mapped[list] = mapped_column(JSONType, default=list)
    guarantee: Mapped[str] = mapped_column(Text, default="")
    logo_url: Mapped[str] = mapped_column(String(1000), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_profile_model.py -v`
Expected: PASS (2 теста).

- [ ] **Step 6: Создать миграцию (проверяется на Postgres)**

Create `backend/alembic/versions/a1b2c3d4e5f6_company_profiles.py`:

```python
"""company profiles

Revision ID: a1b2c3d4e5f6
Revises: c3f910d2a801
Create Date: 2026-06-13 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = 'c3f910d2a801'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'company_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('org_name', sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column('inn', sa.String(length=20), server_default=sa.text("''"), nullable=False),
        sa.Column('contacts', postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('bank_requisites', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('utp', postgresql.JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('cases', postgresql.JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('guarantee', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('logo_url', sa.String(length=1000), server_default=sa.text("''"), nullable=False),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('company_profiles')
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/profile/__init__.py backend/app/profile/models.py backend/tests/conftest.py backend/tests/test_profile_model.py backend/alembic/versions/a1b2c3d4e5f6_company_profiles.py
git commit -m "feat(phase4a): CompanyProfile model + migration"
```

---

## Task 3: Профиль — схемы, сервис, роутер (GET/PUT /api/profile)

**Files:**
- Create: `backend/app/profile/schemas.py`
- Create: `backend/app/profile/service.py`
- Create: `backend/app/profile/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_profile_api.py`

- [ ] **Step 1: Написать падающий тест API**

Create `backend/tests/test_profile_api.py`:

```python
from app.auth.models import User
from app.core.security import create_access_token


def _user(db_session, role="estimator", email=None):
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active")
    db_session.add(u)
    db_session.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_get_profile_returns_empty_when_absent(client, db_session):
    u = _user(db_session)
    r = client.get("/api/profile", headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["org_name"] == ""
    assert r.json()["contacts"] == {}


def test_put_profile_upserts(client, db_session):
    u = _user(db_session)
    payload = {
        "org_name": "ООО Ромашка",
        "inn": "7701234567",
        "contacts": {"phone": "+7 900 000-00-00", "email": "a@b.ru"},
        "utp": ["Гарантия 5 лет", "Свои бригады"],
        "cases": ["ЖК Заря — 1200 м²"],
        "guarantee": "5 лет на работы",
        "bank_requisites": "р/с 4070...",
    }
    r = client.put("/api/profile", json=payload, headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["org_name"] == "ООО Ромашка"
    assert r.json()["utp"] == ["Гарантия 5 лет", "Свои бригады"]
    # второй PUT обновляет тот же профиль (не создаёт второй)
    r2 = client.put("/api/profile", json={**payload, "org_name": "ООО Лютик"}, headers=_hdr(u))
    assert r2.status_code == 200
    assert r2.json()["org_name"] == "ООО Лютик"
    r3 = client.get("/api/profile", headers=_hdr(u))
    assert r3.json()["org_name"] == "ООО Лютик"


def test_profile_requires_auth(client):
    assert client.get("/api/profile").status_code == 401
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_profile_api.py -v`
Expected: FAIL (404 на `/api/profile` — роутер не подключён).

- [ ] **Step 3: Создать схемы**

Create `backend/app/profile/schemas.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContactInfo(BaseModel):
    phone: str = ""
    email: str = ""
    address: str = ""
    site: str = ""


class ProfileIn(BaseModel):
    org_name: str = Field(default="", max_length=500)
    inn: str = Field(default="", max_length=20)
    contacts: ContactInfo = Field(default_factory=ContactInfo)
    bank_requisites: str = ""
    utp: list[str] = Field(default_factory=list)
    cases: list[str] = Field(default_factory=list)
    guarantee: str = ""
    logo_url: str = Field(default="", max_length=1000)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_name: str
    inn: str
    contacts: dict
    bank_requisites: str
    utp: list[str]
    cases: list[str]
    guarantee: str
    logo_url: str
    updated_at: datetime
```

- [ ] **Step 4: Создать сервис**

Create `backend/app/profile/service.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.profile import models, schemas


def get_profile(db: Session, user_id: int) -> models.CompanyProfile | None:
    return db.scalars(
        select(models.CompanyProfile).where(models.CompanyProfile.user_id == user_id)
    ).first()


def upsert_profile(
    db: Session, user_id: int, body: schemas.ProfileIn
) -> models.CompanyProfile:
    profile = get_profile(db, user_id)
    if profile is None:
        profile = models.CompanyProfile(user_id=user_id)
        db.add(profile)
    profile.org_name = body.org_name
    profile.inn = body.inn
    profile.contacts = body.contacts.model_dump()
    profile.bank_requisites = body.bank_requisites
    profile.utp = body.utp
    profile.cases = body.cases
    profile.guarantee = body.guarantee
    profile.logo_url = body.logo_url
    db.commit()
    db.refresh(profile)
    return profile
```

- [ ] **Step 5: Создать роутер**

Create `backend/app/profile/router.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.profile import schemas, service

router = APIRouter(prefix="/api", tags=["profile"])

# Пустой профиль для пользователя без сохранённых реквизитов (GET до первого PUT).
_EMPTY = schemas.ProfileOut(
    id=0, org_name="", inn="", contacts={}, bank_requisites="",
    utp=[], cases=[], guarantee="", logo_url="",
    updated_at="1970-01-01T00:00:00Z",  # type: ignore[arg-type]
)


@router.get("/profile", response_model=schemas.ProfileOut)
def get_profile(db: Session = Depends(get_db), user: User = Depends(require_active)):
    profile = service.get_profile(db, user.id)
    if profile is None:
        return _EMPTY
    return profile


@router.put("/profile", response_model=schemas.ProfileOut)
def put_profile(
    body: schemas.ProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    return service.upsert_profile(db, user.id, body)
```

> Примечание: `_EMPTY.updated_at` строкой — Pydantic v2 распарсит ISO-строку в `datetime` при конструировании. Если линтер ругается на тип — заменить на `datetime(1970, 1, 1, tzinfo=UTC)` с импортом `from datetime import UTC, datetime` и убрать `# type: ignore`.

- [ ] **Step 6: Подключить роутер**

В `backend/app/main.py`:

```python
from app.estimates.router import router as estimates_router
from app.profile.router import router as profile_router
```
и ниже:
```python
app.include_router(estimates_router)
app.include_router(profile_router)
```

- [ ] **Step 7: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_profile_api.py -v`
Expected: PASS (3 теста).

- [ ] **Step 8: Commit**

```bash
git add backend/app/profile/schemas.py backend/app/profile/service.py backend/app/profile/router.py backend/app/main.py backend/tests/test_profile_api.py
git commit -m "feat(phase4a): profile API (GET/PUT /api/profile, upsert)"
```

---

## Task 4: Поле Estimate.proposal + миграция

**Files:**
- Modify: `backend/app/estimates/models.py`
- Create: `backend/tests/test_estimate_proposal_field.py`
- Create: `backend/alembic/versions/b2c3d4e5f6a7_estimate_proposal.py`

- [ ] **Step 1: Написать падающий тест**

Create `backend/tests/test_estimate_proposal_field.py`:

```python
from app.auth.models import User
from app.estimates.models import Estimate


def _user(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    return u


def test_proposal_defaults_none_and_stores_dict(db_session):
    u = _user(db_session)
    est = Estimate(owner_id=u.id, object_name="Объект")
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    assert est.proposal is None

    est.proposal = {"title": "Ремонт под ключ", "advantages": ["быстро", "качественно"]}
    db_session.commit()
    db_session.refresh(est)
    assert est.proposal["title"] == "Ремонт под ключ"
    assert est.proposal["advantages"] == ["быстро", "качественно"]
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_estimate_proposal_field.py -v`
Expected: FAIL (`AttributeError: proposal` / поле не сохраняется).

- [ ] **Step 3: Добавить поле в модель**

В `backend/app/estimates/models.py` добавить импорт типа сверху:

```python
from app.core.db import Base
from app.core.types import JSONType
```

В класс `Estimate` после `created_at` (перед `branches = relationship(...)`):

```python
    proposal: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
```

- [ ] **Step 4: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_estimate_proposal_field.py -v`
Expected: PASS.

- [ ] **Step 5: Создать миграцию**

Create `backend/alembic/versions/b2c3d4e5f6a7_estimate_proposal.py`:

```python
"""estimate proposal field

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13 10:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('estimates', sa.Column('proposal', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('estimates', 'proposal')
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/estimates/models.py backend/tests/test_estimate_proposal_field.py backend/alembic/versions/b2c3d4e5f6a7_estimate_proposal.py
git commit -m "feat(phase4a): Estimate.proposal JSONB field + migration"
```

---

## Task 5: AI-генерация блоков КП (Claude замокан)

**Files:**
- Create: `backend/app/proposals/__init__.py` (пустой)
- Create: `backend/app/proposals/schemas.py`
- Create: `backend/app/proposals/service.py`
- Create: `backend/tests/test_proposal_service.py`

- [ ] **Step 1: Написать падающий тест сервиса**

Create `backend/tests/test_proposal_service.py`:

```python
import pytest

from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.profile.models import CompanyProfile
from app.proposals import service


def _estimate_with_lines(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Квартира 80 м²")
    branch = EstimateBranch(name="Базовая")
    section = EstimateSection(name="Демонтаж")
    section.lines.append(
        EstimateLine(name="Демонтаж перегородок", unit="м²", qty=20, work_price=500, material_price=0)
    )
    branch.sections.append(section)
    est.branches.append(branch)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    profile = CompanyProfile(
        user_id=u.id, org_name="ООО Ромашка", utp=["Гарантия 5 лет"], guarantee="5 лет"
    )
    db_session.add(profile)
    db_session.commit()
    return est, profile


def test_build_prompt_includes_object_lines_and_profile(db_session):
    est, profile = _estimate_with_lines(db_session)
    prompt = service.build_prompt(est, profile)
    assert "Квартира 80 м²" in prompt
    assert "Демонтаж перегородок" in prompt
    assert "ООО Ромашка" in prompt
    assert "Гарантия 5 лет" in prompt


def test_generate_proposal_writes_blocks(db_session, monkeypatch):
    est, profile = _estimate_with_lines(db_session)
    monkeypatch.setattr(service.settings, "anthropic_api_key", "sk-test")
    fake = {
        "title": "Ремонт под ключ", "subtitle": "Качество и сроки",
        "pain": "Долго и дорого", "solution": "Сделаем за 30 дней",
        "advantages": ["Свои бригады"], "terms": "Аванс 30%", "cta": "Свяжитесь с нами",
    }
    monkeypatch.setattr(service, "_call_claude", lambda prompt: fake)
    result = service.generate_proposal(est, profile)
    assert result["title"] == "Ремонт под ключ"
    assert result["advantages"] == ["Свои бригады"]


def test_generate_proposal_raises_when_no_key(db_session, monkeypatch):
    est, profile = _estimate_with_lines(db_session)
    monkeypatch.setattr(service.settings, "anthropic_api_key", "")
    with pytest.raises(service.ProposalAINotConfigured):
        service.generate_proposal(est, profile)
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_proposal_service.py -v`
Expected: FAIL (`ModuleNotFoundError: app.proposals`).

- [ ] **Step 3: Создать схемы блоков КП**

Create `backend/app/proposals/__init__.py` (пустой файл).

Create `backend/app/proposals/schemas.py`:

```python
from pydantic import BaseModel, ConfigDict


class ProposalBlocks(BaseModel):
    """Маркетинговые блоки КП. Все опциональны (AI или ручной ввод)."""
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    subtitle: str = ""
    pain: str = ""
    solution: str = ""
    advantages: list[str] = []
    terms: str = ""
    cta: str = ""


class ProposalPatch(BaseModel):
    """Частичная ручная правка. None-поля не трогаются."""
    title: str | None = None
    subtitle: str | None = None
    pain: str | None = None
    solution: str | None = None
    advantages: list[str] | None = None
    terms: str | None = None
    cta: str | None = None
```

- [ ] **Step 4: Создать сервис AI-генерации**

Create `backend/app/proposals/service.py`:

```python
import json

from app.core.config import settings
from app.estimates import models as est_models
from app.estimates import service as est_service
from app.profile import models as profile_models
from app.proposals.schemas import ProposalBlocks

MODEL = "claude-opus-4-8"


class ProposalAINotConfigured(Exception):
    """ANTHROPIC_API_KEY не задан — AI-генерация недоступна."""


class ProposalAIError(Exception):
    """Ошибка вызова Claude (сеть/таймаут/невалидный ответ)."""


def build_prompt(
    estimate: est_models.Estimate, profile: profile_models.CompanyProfile | None
) -> str:
    """Промпт из сметы (объект, позиции, итог) и профиля исполнителя."""
    lines: list[str] = []
    for branch in estimate.branches:
        for section in branch.sections:
            for ln in section.lines:
                lines.append(f"- {section.name}: {ln.name} ({ln.qty} {ln.unit})")
    totals = est_service.compute_totals(estimate)

    profile_parts: list[str] = []
    if profile is not None:
        if profile.org_name:
            profile_parts.append(f"Компания: {profile.org_name}")
        if profile.utp:
            profile_parts.append("УТП: " + "; ".join(profile.utp))
        if profile.cases:
            profile_parts.append("Кейсы: " + "; ".join(profile.cases))
        if profile.guarantee:
            profile_parts.append(f"Гарантия: {profile.guarantee}")
    profile_block = "\n".join(profile_parts) or "(профиль исполнителя не заполнен)"

    return (
        "Ты — копирайтер строительной компании. Составь продающее коммерческое "
        "предложение по смете. Верни блоки на русском языке в тоне делового КП "
        "(заголовок-выгода, боль клиента, решение-результат, УТП, преимущества, "
        "условия, призыв к действию).\n\n"
        f"Объект: {estimate.object_name or '(не указан)'}\n"
        f"Итоговая стоимость: {totals['total']} руб.\n\n"
        "Состав работ:\n" + ("\n".join(lines) or "(позиции не добавлены)") + "\n\n"
        "Об исполнителе:\n" + profile_block
    )


def _call_claude(prompt: str) -> dict:
    """Единственный seam к Claude API. В тестах замокан monkeypatch'ем."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            output_config={"format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
            timeout=60.0,
        )
    except anthropic.APIError as exc:  # сеть/таймаут/перегрузка
        raise ProposalAIError(str(exc)) from exc
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProposalAIError("Claude вернул невалидный JSON") from exc


_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "pain": {"type": "string"},
        "solution": {"type": "string"},
        "advantages": {"type": "array", "items": {"type": "string"}},
        "terms": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["title", "subtitle", "pain", "solution", "advantages", "terms", "cta"],
    "additionalProperties": False,
}


def generate_proposal(
    estimate: est_models.Estimate, profile: profile_models.CompanyProfile | None
) -> dict:
    if not settings.anthropic_api_key:
        raise ProposalAINotConfigured("AI не настроен")
    prompt = build_prompt(estimate, profile)
    blocks = _call_claude(prompt)
    return ProposalBlocks.model_validate(blocks).model_dump()
```

> Модель `claude-opus-4-8` — дефолт по skill claude-api (пользователь не называл другую). `output_config.format` — structured output (актуальный API, не устаревший `output_format`). Реальный вызов в тестах не выполняется: `_call_claude` замокан.

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_proposal_service.py -v`
Expected: PASS (3 теста).

- [ ] **Step 6: Commit**

```bash
git add backend/app/proposals/__init__.py backend/app/proposals/schemas.py backend/app/proposals/service.py backend/tests/test_proposal_service.py
git commit -m "feat(phase4a): proposal AI generation service (Claude mocked)"
```

---

## Task 6: Роутер КП (generate / patch)

**Files:**
- Create: `backend/app/proposals/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_proposal_api.py`

- [ ] **Step 1: Написать падающий тест API**

Create `backend/tests/test_proposal_api.py`:

```python
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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_proposal_api.py -v`
Expected: FAIL (404 — роутер не подключён).

- [ ] **Step 3: Создать роутер**

Create `backend/app/proposals/router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import service as est_service
from app.profile import service as profile_service
from app.proposals import schemas, service

router = APIRouter(prefix="/api", tags=["proposals"])


@router.post("/estimates/{estimate_id}/proposal/generate")
def generate(
    estimate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    profile = profile_service.get_profile(db, user.id)
    try:
        blocks = service.generate_proposal(est, profile)
    except service.ProposalAINotConfigured:
        raise HTTPException(status_code=503, detail="AI не настроен")
    except service.ProposalAIError as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка AI: {exc}")
    est.proposal = blocks
    db.commit()
    return blocks


@router.patch("/estimates/{estimate_id}/proposal")
def patch_proposal(
    estimate_id: int,
    body: schemas.ProposalPatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    current = dict(est.proposal or {})
    current.update(body.model_dump(exclude_unset=True))
    est.proposal = current
    db.commit()
    return current
```

- [ ] **Step 4: Подключить роутер**

В `backend/app/main.py`:

```python
from app.profile.router import router as profile_router
from app.proposals.router import router as proposals_router
```
и:
```python
app.include_router(profile_router)
app.include_router(proposals_router)
```

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_proposal_api.py -v`
Expected: PASS (4 теста).

- [ ] **Step 6: Commit**

```bash
git add backend/app/proposals/router.py backend/app/main.py backend/tests/test_proposal_api.py
git commit -m "feat(phase4a): proposal endpoints (generate/patch)"
```

---

## Task 7: Контекст экспорта + Excel-генератор

**Files:**
- Create: `backend/app/export/__init__.py` (пустой)
- Create: `backend/app/export/context.py`
- Create: `backend/app/export/excel.py`
- Create: `backend/tests/test_export_excel.py`

- [ ] **Step 1: Написать падающий тест Excel + контекста**

Create `backend/tests/test_export_excel.py`:

```python
import io

from openpyxl import load_workbook

from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.export import context as ctx
from app.export.excel import render_xlsx


def _estimate(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Квартира")
    branch = EstimateBranch(name="Базовая")
    section = EstimateSection(name="Стены", markup_percent=10)
    section.lines.append(
        EstimateLine(name="Штукатурка", unit="м²", qty=10, work_price=300,
                     material_price=100, purchase_price_snapshot=80)
    )
    branch.sections.append(section)
    est.branches.append(branch)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


def test_public_context_strips_margin_and_purchase(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=True)
    assert context["totals"]["margin"] is None
    assert context["totals"]["purchase"] is None
    for section in context["sections"]:
        assert section["totals"]["margin"] is None
        for line in section["lines"]:
            assert "purchase_price_snapshot" not in line


def test_private_context_keeps_margin(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=False)
    assert context["totals"]["margin"] is not None


def test_render_xlsx_is_valid_workbook(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="estimate", public=False)
    data = render_xlsx(context)
    assert isinstance(data, bytes) and len(data) > 0
    wb = load_workbook(io.BytesIO(data))
    ws = wb.active
    text = "\n".join(
        str(c.value) for row in ws.iter_rows() for c in row if c.value is not None
    )
    assert "Квартира" in text
    assert "Штукатурка" in text
    assert "Стены" in text
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_export_excel.py -v`
Expected: FAIL (`ModuleNotFoundError: app.export`).

- [ ] **Step 3: Создать контекст-билдер**

Create `backend/app/export/__init__.py` (пустой файл).

Create `backend/app/export/context.py`:

```python
"""Единый контекст для Excel/HTML/PDF. Для public режет закупку и маржу."""
from app.estimates import models, service

LEVELS = ("full", "cover", "estimate")


def build_export_context(
    est: models.Estimate, *, level: str = "full", public: bool = False
) -> dict:
    if level not in LEVELS:
        level = "full"
    totals = service.compute_totals(est)
    totals_by_section = {s["section_id"]: s for s in totals["sections"]}

    sections_out = []
    for branch in est.branches:
        for section in branch.sections:
            st = totals_by_section.get(section.id, {})
            lines_out = []
            for ln in section.lines:
                line = {
                    "name": ln.name,
                    "unit": ln.unit,
                    "qty": ln.qty,
                    "work_price": ln.work_price,
                    "material_price": ln.material_price,
                }
                if not public:
                    line["purchase_price_snapshot"] = ln.purchase_price_snapshot
                lines_out.append(line)
            sections_out.append({
                "name": section.name,
                "lines": lines_out,
                "totals": _section_totals(st, public),
            })

    return {
        "object_name": est.object_name,
        "vat_enabled": est.vat_enabled,
        "vat_rate": est.vat_rate,
        "level": level,
        "public": public,
        "proposal": est.proposal or {},
        "sections": sections_out,
        "totals": _estimate_totals(totals, public),
    }


def _section_totals(st: dict, public: bool) -> dict:
    return {
        "materials": st.get("materials"),
        "works": st.get("works"),
        "total": st.get("total"),
        "purchase": None if public else st.get("purchase"),
        "margin": None if public else st.get("margin"),
    }


def _estimate_totals(totals: dict, public: bool) -> dict:
    return {
        "materials": totals["materials"],
        "works": totals["works"],
        "subtotal": totals["subtotal"],
        "vat": totals["vat"],
        "total": totals["total"],
        "purchase": None if public else totals["purchase"],
        "margin": None if public else totals["margin"],
    }
```

- [ ] **Step 4: Создать Excel-генератор**

Create `backend/app/export/excel.py`:

```python
import io

from openpyxl import Workbook
from openpyxl.styles import Font


def _num(value) -> float:
    return float(value) if value is not None else 0.0


def render_xlsx(context: dict) -> bytes:
    """Лист: шапка → таблица разделов/позиций → итоги → место под подпись."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Смета"

    ws["A1"] = "Смета / коммерческое предложение"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Объект: {context['object_name']}"

    proposal = context.get("proposal") or {}
    row = 4
    if context["level"] in ("full", "cover") and proposal.get("title"):
        ws.cell(row=row, column=1, value=proposal["title"]).font = Font(bold=True, size=12)
        row += 1
        if proposal.get("subtitle"):
            ws.cell(row=row, column=1, value=proposal["subtitle"])
            row += 1
        row += 1

    headers = ["Наименование", "Ед.", "Кол-во", "Материалы", "Работы", "Сумма"]
    for col, title in enumerate(headers, start=1):
        ws.cell(row=row, column=col, value=title).font = Font(bold=True)
    row += 1

    for section in context["sections"]:
        ws.cell(row=row, column=1, value=section["name"]).font = Font(bold=True)
        row += 1
        for ln in section["lines"]:
            mat = _num(ln["material_price"]) * _num(ln["qty"])
            work = _num(ln["work_price"]) * _num(ln["qty"])
            ws.cell(row=row, column=1, value=ln["name"])
            ws.cell(row=row, column=2, value=ln["unit"])
            ws.cell(row=row, column=3, value=_num(ln["qty"]))
            ws.cell(row=row, column=4, value=mat)
            ws.cell(row=row, column=5, value=work)
            ws.cell(row=row, column=6, value=mat + work)
            row += 1
        st = section["totals"]
        ws.cell(row=row, column=5, value="Итого по разделу:").font = Font(bold=True)
        ws.cell(row=row, column=6, value=_num(st["total"])).font = Font(bold=True)
        row += 1

    totals = context["totals"]
    row += 1
    ws.cell(row=row, column=5, value="Без НДС:")
    ws.cell(row=row, column=6, value=_num(totals["subtotal"]))
    row += 1
    if context["vat_enabled"]:
        ws.cell(row=row, column=5, value="НДС:")
        ws.cell(row=row, column=6, value=_num(totals["vat"]))
        row += 1
    ws.cell(row=row, column=5, value="ВСЕГО:").font = Font(bold=True)
    ws.cell(row=row, column=6, value=_num(totals["total"])).font = Font(bold=True)
    row += 3
    ws.cell(row=row, column=1, value="Подпись: ____________________   М.П.")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_export_excel.py -v`
Expected: PASS (3 теста).

- [ ] **Step 6: Commit**

```bash
git add backend/app/export/__init__.py backend/app/export/context.py backend/app/export/excel.py backend/tests/test_export_excel.py
git commit -m "feat(phase4a): export context builder + openpyxl Excel generator"
```

---

## Task 8: HTML-шаблон + рендер (Jinja2 + weasyprint PDF)

**Files:**
- Create: `backend/app/export/templates/proposal.html`
- Create: `backend/app/export/render.py`
- Create: `backend/tests/test_export_render.py`

- [ ] **Step 1: Написать падающий тест рендера**

Create `backend/tests/test_export_render.py`:

```python
import pytest

from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.export import context as ctx
from app.export import render


def _estimate(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Дом 120 м²")
    est.proposal = {"title": "Ремонт под ключ", "cta": "Звоните"}
    branch = EstimateBranch(name="Базовая")
    section = EstimateSection(name="Полы", markup_percent=0)
    section.lines.append(
        EstimateLine(name="Стяжка", unit="м²", qty=50, work_price=400,
                     material_price=200, purchase_price_snapshot=150)
    )
    branch.sections.append(section)
    est.branches.append(branch)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


def test_render_html_full_includes_proposal_and_lines(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=False)
    html = render.render_html(context)
    assert "Ремонт под ключ" in html
    assert "Стяжка" in html
    assert "Дом 120 м²" in html


def test_public_html_has_no_margin_or_purchase(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=True)
    html = render.render_html(context)
    assert "Маржа" not in html
    assert "Закупка" not in html
    assert "150" not in html  # закупочная цена не утекла


def test_watermark_present_when_enabled(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=True)
    html = render.render_html(context, watermark="ОБРАЗЕЦ")
    assert "ОБРАЗЕЦ" in html


def test_html_to_pdf_signature(db_session):
    weasyprint = pytest.importorskip("weasyprint")  # noqa: F841
    try:
        pdf = render.html_to_pdf("<html><body><h1>Тест</h1></body></html>")
    except OSError:
        pytest.skip("системные библиотеки weasyprint недоступны")
    assert pdf[:4] == b"%PDF"
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_export_render.py -v`
Expected: FAIL (`ModuleNotFoundError` / нет `render`).

- [ ] **Step 3: Создать Jinja2-шаблон**

Create `backend/app/export/templates/proposal.html`:

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: "DejaVu Serif", Georgia, serif; color: #1c1917; margin: 32px; }
    h1, h2 { font-family: "DejaVu Serif", Georgia, serif; }
    .subtitle { color: #57534e; font-size: 14px; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 12px; }
    th, td { border-bottom: 1px solid #d6d3d1; padding: 6px 8px; text-align: left; }
    td.num, th.num { text-align: right; }
    .section-name td { font-weight: bold; background: #f5f5f4; }
    .totals { margin-top: 16px; text-align: right; font-size: 13px; }
    .totals .grand { font-size: 18px; font-weight: bold; }
    .sign { margin-top: 48px; }
    .watermark {
      position: fixed; top: 40%; left: 10%; font-size: 80px; color: rgba(0,0,0,0.08);
      transform: rotate(-30deg); z-index: -1;
    }
    .block { margin: 12px 0; }
  </style>
</head>
<body>
  {% if watermark %}<div class="watermark">{{ watermark }}</div>{% endif %}

  {% if level in ("full", "cover") and proposal.title %}
    <h1>{{ proposal.title }}</h1>
    {% if proposal.subtitle %}<p class="subtitle">{{ proposal.subtitle }}</p>{% endif %}
  {% else %}
    <h1>Смета</h1>
  {% endif %}
  <p>Объект: {{ object_name }}</p>

  {% if level == "full" %}
    {% if proposal.pain %}<div class="block"><strong>Задача:</strong> {{ proposal.pain }}</div>{% endif %}
    {% if proposal.solution %}<div class="block"><strong>Решение:</strong> {{ proposal.solution }}</div>{% endif %}
    {% if proposal.advantages %}
      <div class="block"><strong>Преимущества:</strong>
        <ul>{% for a in proposal.advantages %}<li>{{ a }}</li>{% endfor %}</ul>
      </div>
    {% endif %}
  {% endif %}

  <table>
    <thead>
      <tr>
        <th>Наименование</th><th>Ед.</th><th class="num">Кол-во</th>
        <th class="num">Материалы</th><th class="num">Работы</th><th class="num">Сумма</th>
      </tr>
    </thead>
    <tbody>
      {% for section in sections %}
        <tr class="section-name"><td colspan="6">{{ section.name }}</td></tr>
        {% for ln in section.lines %}
          <tr>
            <td>{{ ln.name }}</td><td>{{ ln.unit }}</td>
            <td class="num">{{ ln.qty }}</td>
            <td class="num">{{ ln.material_price }}</td>
            <td class="num">{{ ln.work_price }}</td>
            <td class="num">{{ section.totals.total }}</td>
          </tr>
        {% endfor %}
      {% endfor %}
    </tbody>
  </table>

  <div class="totals">
    <div>Без НДС: {{ totals.subtotal }}</div>
    {% if vat_enabled %}<div>НДС: {{ totals.vat }}</div>{% endif %}
    <div class="grand">ВСЕГО: {{ totals.total }}</div>
  </div>

  {% if level == "full" and proposal.terms %}
    <div class="block"><strong>Условия:</strong> {{ proposal.terms }}</div>
  {% endif %}
  {% if level in ("full", "cover") and proposal.cta %}
    <div class="block">{{ proposal.cta }}</div>
  {% endif %}

  <div class="sign">Подпись: ____________________&nbsp;&nbsp;&nbsp;М.П.</div>
</body>
</html>
```

> Шаблон НЕ выводит закупку/маржу ни на каком уровне — публичная безопасность встроена в разметку (контекст для public их и так зануляет, но шаблон их вообще не печатает).

- [ ] **Step 4: Создать рендер**

Create `backend/app/export/render.py`:

```python
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def render_html(context: dict, *, watermark: str = "") -> str:
    template = _env.get_template("proposal.html")
    return template.render(watermark=watermark, **context)


def html_to_pdf(html: str) -> bytes:
    """Рендер HTML → PDF через weasyprint. Импорт ленивый (тяжёлые sys-libs)."""
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
```

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_export_render.py -v`
Expected: PASS — 3 теста HTML PASS; `test_html_to_pdf_signature` PASS если weasyprint+libs есть, иначе SKIP.

- [ ] **Step 6: Commit**

```bash
git add backend/app/export/templates/proposal.html backend/app/export/render.py backend/tests/test_export_render.py
git commit -m "feat(phase4a): Jinja2 proposal template + html/pdf render"
```

---

## Task 9: Эндпоинты экспорта (xlsx / pdf)

**Files:**
- Create: `backend/app/export/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_export_api.py`

- [ ] **Step 1: Написать падающий тест**

Create `backend/tests/test_export_api.py`:

```python
from app.auth.models import User
from app.core.security import create_access_token
from app.estimates.models import Estimate
from app.export import router as export_router


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
    # мок weasyprint — эндпоинт тестируем без системных библиотек
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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_export_api.py -v`
Expected: FAIL (404 — роутер не подключён).

- [ ] **Step 3: Создать роутер**

Create `backend/app/export/router.py`:

```python
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import service as est_service
from app.export import context as ctx
from app.export import render
from app.export.excel import render_xlsx

router = APIRouter(prefix="/api", tags=["export"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/estimates/{estimate_id}/export.xlsx")
def export_xlsx(
    estimate_id: int,
    level: str = "full",
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    context = ctx.build_export_context(est, level=level, public=False)
    data = render_xlsx(context)
    return Response(
        content=data,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="estimate-{est.id}.xlsx"'},
    )


@router.get("/estimates/{estimate_id}/export.pdf")
def export_pdf(
    estimate_id: int,
    level: str = "full",
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    context = ctx.build_export_context(est, level=level, public=False)
    html = render.render_html(context)
    pdf = render.html_to_pdf(html)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="estimate-{est.id}.pdf"'},
    )
```

- [ ] **Step 4: Подключить роутер**

В `backend/app/main.py`:

```python
from app.proposals.router import router as proposals_router
from app.export.router import router as export_router
```
и:
```python
app.include_router(proposals_router)
app.include_router(export_router)
```

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_export_api.py -v`
Expected: PASS (3 теста).

- [ ] **Step 6: Commit**

```bash
git add backend/app/export/router.py backend/app/main.py backend/tests/test_export_api.py
git commit -m "feat(phase4a): export endpoints (xlsx/pdf)"
```

---

## Task 10: Модель PublicLink + миграция

**Files:**
- Create: `backend/app/publiclinks/__init__.py` (пустой)
- Create: `backend/app/publiclinks/models.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_publiclink_model.py`
- Create: `backend/alembic/versions/c3d4e5f6a7b8_public_links.py`

- [ ] **Step 1: Написать падающий тест модели**

Create `backend/tests/test_publiclink_model.py`:

```python
from app.auth.models import User
from app.estimates.models import Estimate
from app.publiclinks.models import PublicLink


def test_public_link_defaults(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Объект")
    db_session.add(est)
    db_session.commit()
    link = PublicLink(estimate_id=est.id, token="abc123")
    db_session.add(link)
    db_session.commit()
    db_session.refresh(link)
    assert link.level == "full"
    assert link.revoked is False
    assert link.watermark_enabled is False
    assert link.expires_at is None
```

- [ ] **Step 2: Зарегистрировать модель в conftest**

В `backend/tests/conftest.py` после импорта profile-моделей:

```python
from app.profile import models as _profile_models  # noqa: F401
from app.publiclinks import models as _publiclink_models  # noqa: F401
```

- [ ] **Step 3: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_publiclink_model.py -v`
Expected: FAIL (`ModuleNotFoundError: app.publiclinks`).

- [ ] **Step 4: Создать модель**

Create `backend/app/publiclinks/__init__.py` (пустой файл).

Create `backend/app/publiclinks/models.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PublicLink(Base):
    __tablename__ = "public_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    level: Mapped[str] = mapped_column(String(20), default="full")
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    watermark_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    watermark_text: Mapped[str] = mapped_column(String(255), default="")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_publiclink_model.py -v`
Expected: PASS.

- [ ] **Step 6: Создать миграцию**

Create `backend/alembic/versions/c3d4e5f6a7b8_public_links.py`:

```python
"""public links

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-13 11:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: str | Sequence[str] | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'public_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('estimate_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('level', sa.String(length=20), server_default=sa.text("'full'"), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'watermark_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False
        ),
        sa.Column(
            'watermark_text', sa.String(length=255), server_default=sa.text("''"), nullable=False
        ),
        sa.Column('revoked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(['estimate_id'], ['estimates.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_public_links_token'), 'public_links', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_public_links_token'), table_name='public_links')
    op.drop_table('public_links')
```

> ⚠️ `server_default` для boolean — `sa.text('false')` (НЕ `'0'`): урок фазы 3a, иначе Postgres DatatypeMismatch.

- [ ] **Step 7: Commit**

```bash
git add backend/app/publiclinks/__init__.py backend/app/publiclinks/models.py backend/tests/conftest.py backend/tests/test_publiclink_model.py backend/alembic/versions/c3d4e5f6a7b8_public_links.py
git commit -m "feat(phase4a): PublicLink model + migration"
```

---

## Task 11: Админ-API публичных ссылок (создать/список/отозвать)

**Files:**
- Create: `backend/app/publiclinks/schemas.py`
- Create: `backend/app/publiclinks/service.py`
- Create: `backend/app/publiclinks/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_publiclinks_api.py`

- [ ] **Step 1: Написать падающий тест API**

Create `backend/tests/test_publiclinks_api.py`:

```python
from app.auth.models import User
from app.core.security import create_access_token
from app.estimates.models import Estimate


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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_publiclinks_api.py -v`
Expected: FAIL (404 — роутер не подключён).

- [ ] **Step 3: Создать схемы**

Create `backend/app/publiclinks/schemas.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicLinkIn(BaseModel):
    level: str = Field(default="full", pattern="^(full|cover|estimate)$")
    expires_at: datetime | None = None
    watermark_enabled: bool = False
    watermark_text: str = Field(default="", max_length=255)


class PublicLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estimate_id: int
    token: str
    level: str
    expires_at: datetime | None
    watermark_enabled: bool
    watermark_text: str
    revoked: bool
    created_at: datetime
```

- [ ] **Step 4: Создать сервис**

Create `backend/app/publiclinks/service.py`:

```python
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.publiclinks import models, schemas


def create_link(db: Session, estimate_id: int, body: schemas.PublicLinkIn) -> models.PublicLink:
    link = models.PublicLink(
        estimate_id=estimate_id,
        token=secrets.token_urlsafe(24),
        level=body.level,
        expires_at=body.expires_at,
        watermark_enabled=body.watermark_enabled,
        watermark_text=body.watermark_text,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def list_links(db: Session, estimate_id: int):
    return db.scalars(
        select(models.PublicLink)
        .where(models.PublicLink.estimate_id == estimate_id)
        .order_by(models.PublicLink.created_at.desc())
    ).all()


def revoke_link(db: Session, link: models.PublicLink) -> None:
    link.revoked = True
    db.commit()


def _expired(link: models.PublicLink) -> bool:
    if link.expires_at is None:
        return False
    exp = link.expires_at
    if exp.tzinfo is None:  # SQLite хранит naive — считаем UTC
        exp = exp.replace(tzinfo=UTC)
    return exp < datetime.now(UTC)


def resolve_token(db: Session, token: str) -> models.PublicLink:
    """Публичный доступ: не найден/отозван → 404; просрочен → 410."""
    link = db.scalars(
        select(models.PublicLink).where(models.PublicLink.token == token)
    ).first()
    if link is None or link.revoked:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    if _expired(link):
        raise HTTPException(status_code=410, detail="Срок действия ссылки истёк")
    return link
```

- [ ] **Step 5: Создать роутер**

Create `backend/app/publiclinks/router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import service as est_service
from app.publiclinks import models, schemas, service

router = APIRouter(prefix="/api", tags=["public-links"])


@router.post(
    "/estimates/{estimate_id}/public-links",
    response_model=schemas.PublicLinkOut,
    status_code=201,
)
def create_public_link(
    estimate_id: int,
    body: schemas.PublicLinkIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    return service.create_link(db, est.id, body)


@router.get(
    "/estimates/{estimate_id}/public-links",
    response_model=list[schemas.PublicLinkOut],
)
def list_public_links(
    estimate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    return service.list_links(db, est.id)


@router.delete("/public-links/{link_id}", status_code=204)
def delete_public_link(
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    link = db.get(models.PublicLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    est = est_service.get_owned_estimate(db, link.estimate_id, user)
    est_service.require_write(est, user)
    service.revoke_link(db, link)
```

- [ ] **Step 6: Подключить роутер**

В `backend/app/main.py`:

```python
from app.export.router import router as export_router
from app.publiclinks.router import router as publiclinks_router
```
и:
```python
app.include_router(export_router)
app.include_router(publiclinks_router)
```

- [ ] **Step 7: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_publiclinks_api.py -v`
Expected: PASS (2 теста).

- [ ] **Step 8: Commit**

```bash
git add backend/app/publiclinks/schemas.py backend/app/publiclinks/service.py backend/app/publiclinks/router.py backend/app/main.py backend/tests/test_publiclinks_api.py
git commit -m "feat(phase4a): public-links admin API (create/list/revoke)"
```

---

## Task 12: Публичный роутер /p/{token} (HTML + PDF, без auth)

**Files:**
- Create: `backend/app/publiclinks/public_router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_public_page.py`

- [ ] **Step 1: Написать падающий тест**

Create `backend/tests/test_public_page.py`:

```python
from datetime import UTC, datetime, timedelta

from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.publiclinks import public_router
from app.publiclinks.models import PublicLink


def _estimate_with_link(db_session, **link_kwargs):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Объект Икс")
    branch = EstimateBranch(name="Базовая")
    section = EstimateSection(name="Кровля", markup_percent=0)
    section.lines.append(
        EstimateLine(name="Монтаж кровли", unit="м²", qty=30, work_price=600,
                     material_price=400, purchase_price_snapshot=333)
    )
    branch.sections.append(section)
    est.branches.append(branch)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    link = PublicLink(estimate_id=est.id, token=link_kwargs.pop("token", "tok-ok"), **link_kwargs)
    db_session.add(link)
    db_session.commit()
    return est, link


def test_public_page_ok_and_no_margin_purchase(client, db_session):
    est, link = _estimate_with_link(db_session, level="full")
    r = client.get(f"/p/{link.token}")
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "Объект Икс" in body
    assert "Монтаж кровли" in body
    assert "Маржа" not in body
    assert "Закупка" not in body
    assert "333" not in body  # закупочная цена не утекла


def test_public_revoked_404(client, db_session):
    est, link = _estimate_with_link(db_session, token="tok-revoked", revoked=True)
    assert client.get(f"/p/{link.token}").status_code == 404


def test_public_expired_410(client, db_session):
    est, link = _estimate_with_link(
        db_session, token="tok-exp", expires_at=datetime.now(UTC) - timedelta(days=1)
    )
    assert client.get(f"/p/{link.token}").status_code == 410


def test_public_unknown_404(client):
    assert client.get("/p/does-not-exist").status_code == 404


def test_public_watermark_present(client, db_session):
    est, link = _estimate_with_link(
        db_session, token="tok-wm", watermark_enabled=True, watermark_text="ЧЕРНОВИК"
    )
    assert "ЧЕРНОВИК" in client.get(f"/p/{link.token}").text


def test_public_pdf_ok(client, db_session, monkeypatch):
    est, link = _estimate_with_link(db_session, token="tok-pdf")
    monkeypatch.setattr(public_router.render, "html_to_pdf", lambda html: b"%PDF-1.7 mock")
    r = client.get(f"/p/{link.token}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python -m pytest tests/test_public_page.py -v`
Expected: FAIL (404 — публичный роутер не подключён).

- [ ] **Step 3: Создать публичный роутер**

Create `backend/app/publiclinks/public_router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.estimates import models as est_models
from app.export import context as ctx
from app.export import render
from app.publiclinks import service

router = APIRouter(tags=["public"])


def _context_for_link(db: Session, token: str) -> tuple[dict, str]:
    link = service.resolve_token(db, token)
    est = db.get(est_models.Estimate, link.estimate_id)
    if est is None:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    context = ctx.build_export_context(est, level=link.level, public=True)
    watermark = link.watermark_text if link.watermark_enabled else ""
    return context, watermark


@router.get("/p/{token}", response_class=HTMLResponse)
def public_page(token: str, db: Session = Depends(get_db)):
    context, watermark = _context_for_link(db, token)
    return HTMLResponse(render.render_html(context, watermark=watermark))


@router.get("/p/{token}/pdf")
def public_pdf(token: str, db: Session = Depends(get_db)):
    context, watermark = _context_for_link(db, token)
    html = render.render_html(context, watermark=watermark)
    pdf = render.html_to_pdf(html)
    return Response(content=pdf, media_type="application/pdf")
```

- [ ] **Step 4: Подключить роутер**

В `backend/app/main.py`:

```python
from app.publiclinks.router import router as publiclinks_router
from app.publiclinks.public_router import router as public_page_router
```
и:
```python
app.include_router(publiclinks_router)
app.include_router(public_page_router)
```

- [ ] **Step 5: Запустить тест — должен пройти**

Run: `python -m pytest tests/test_public_page.py -v`
Expected: PASS (6 тестов).

- [ ] **Step 6: Прогнать ВСЕ тесты бэкенда**

Run: `python -m pytest -q`
Expected: все тесты PASS (PDF-рендер тест из Task 8 может быть SKIPPED без weasyprint-libs).

- [ ] **Step 7: Commit**

```bash
git add backend/app/publiclinks/public_router.py backend/app/main.py backend/tests/test_public_page.py
git commit -m "feat(phase4a): public proposal page + pdf (/p/{token})"
```

---

## Финальная проверка фазы 4a

После всех задач:

- [ ] **Линт:** `python -m ruff check app tests` (из `backend/`) — без ошибок (если ruff в проекте настроен).
- [ ] **Полный прогон тестов:** `python -m pytest -q` — зелёно.
- [ ] **Проверка миграций на Postgres (КРИТИЧНО — урок 3a):** поднять dev-стек и применить миграции на реальном Postgres, убедиться что три новые миграции (`a1b2c3d4e5f6` → `b2c3d4e5f6a7` → `c3d4e5f6a7b8`) накатываются без ошибок:
  ```bash
  docker compose up -d db backend
  docker compose exec backend alembic upgrade head
  docker compose exec backend alembic current   # должна быть c3d4e5f6a7b8 (head)
  ```
  Если есть DatatypeMismatch на boolean — проверить `server_default=sa.text('false')` (не `'0'`).
- [ ] **Финальный холистический код-ревью** всей ветки (subagent-driven: финальный reviewer).
- [ ] **Push + PR** (пользователь сам мержит PR по порядку и переключает default-ветку).

---

## Self-Review плана (выполнено автором)

**Покрытие спека:**
- CompanyProfile (модель/API, один на пользователя) → Task 2, 3 ✓
- Estimate.proposal JSONB → Task 4 ✓
- AI-генерация (Claude SDK, замокан, ключ опционален, 503 без ключа, 502 при ошибке) → Task 5, 6 ✓
- PATCH ручная правка/частичная → Task 6 ✓
- Excel (openpyxl, шапка/позиции/итоги, уровни) → Task 7 ✓
- Один HTML-шаблон → публичная страница + PDF (weasyprint); три уровня → Task 8, 9, 12 ✓
- Публичный вывод без закупки/маржи (контекст + шаблон) → Task 7 (context), 8 (template), 12 (тест утечки) ✓
- PublicLink (token, level, expires_at, watermark, revoked) → Task 10 ✓
- Публичные ссылки API (create/list/revoke) + публичный роутер (404/410, водяной знак) → Task 11, 12 ✓
- Экспорт/публичный доступ к чужой смете → 404 → Task 9, 11 ✓
- Новые зависимости + Dockerfile sys-deps + ANTHROPIC_API_KEY → Task 1 ✓
- Миграции вручную, проверка на Postgres → каждая миграционная задача + финальная проверка ✓

**Согласованность типов:** `build_export_context(est, *, level, public)` — единая сигнатура (Task 7), используется в Task 9, 12. `_call_claude(prompt) -> dict` — seam, замокан в Task 5, 6. `render_html(context, *, watermark)` / `html_to_pdf(html)` (Task 8) — используются в Task 9, 12. `resolve_token` (Task 11) → Task 12. Цепочка миграций: `c3f910d2a801` → `a1b2c3d4e5f6` → `b2c3d4e5f6a7` → `c3d4e5f6a7b8`.

**Без плейсхолдеров:** весь код приведён полностью.
