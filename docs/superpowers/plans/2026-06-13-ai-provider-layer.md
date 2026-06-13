# Слой AI-провайдеров (VseGPT/AITunnel) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Конфигурируемый из админки слой «провайдер + модель на цель» поверх OpenAI-совместимых агрегаторов VseGPT/AITunnel, с моделью-роутером (советником), шифрованными ключами и фолбэком; генерация КП переезжает с Anthropic на этот слой.

**Architecture:** Новый модуль `backend/app/ai/` с тремя таблицами (`AIProvider`, `AIModel`, `AIPurpose`), httpx-клиентом к `/v1/chat/completions`, диспетчером `call_llm(db, purpose_key, messages, json_schema?)` с резолвом цель→модель→провайдер и фолбэком, роутером-советником и админ-API под `require_admin`. Ключи шифруются Fernet (от `SECRET_KEY`).

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, httpx (есть), cryptography (новая), pytest (httpx мокается через `httpx.MockTransport` — без сети и без respx), Postgres/SQLite.

---

## Соглашения (как фаза 4a)

- Auth: `from app.auth.deps import require_admin` → `user: User = Depends(require_admin)`.
- DB: `from app.core.db import get_db, Base`; кросс-диалектный JSON — `from app.core.types import JSONType` (не нужен здесь, поля скалярные).
- Тесты SQLite (conftest), новые модели регистрируются в `conftest.py`.
- Хелперы в тест-файлах:
  ```python
  from app.auth.models import User
  from app.core.security import create_access_token
  def _admin(db_session):
      u = User(email="adm@x.ru", name="A", role="admin", status="active")
      db_session.add(u); db_session.commit(); return u
  def _hdr(u): return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}
  ```
- Запуск: из `backend/` → `python -m pytest tests/<file> -v`. Текущий alembic head — `c3d4e5f6a7b8` (public_links).
- HTTP в тестах НИКОГДА не ходит в сеть: `httpx.MockTransport` (встроен в httpx) либо monkeypatch на `client.chat_completion`.

## File Structure

| Файл | Ответственность |
|---|---|
| `backend/requirements.txt` | + `cryptography`, − `anthropic` |
| `backend/app/ai/errors.py` | `AINotConfigured`, `AIError` |
| `backend/app/ai/crypto.py` | `encrypt`/`decrypt` (Fernet от SECRET_KEY) |
| `backend/app/ai/models.py` | `AIProvider`, `AIModel`, `AIPurpose` |
| `backend/app/ai/schemas.py` | Pydantic-схемы провайдеров/моделей/целей/рекомендаций |
| `backend/app/ai/client.py` | `chat_completion`, `list_models` (httpx) |
| `backend/app/ai/service.py` | `call_llm` (резолв + фолбэк) |
| `backend/app/ai/router_advisor.py` | `recommend_models` (советник) |
| `backend/app/ai/router.py` | админ-API `/api/ai/*` |
| `backend/alembic/versions/d4e5f6a7b8c9_ai_provider_layer.py` | 3 таблицы + сид 4 целей |
| `backend/app/proposals/service.py` | перенос `generate_proposal` на `call_llm` |
| `backend/app/proposals/router.py` | маппинг `ai`-исключений на 503/502 |
| `backend/app/main.py` | подключить `ai_router` |
| `backend/tests/conftest.py` | регистрация `app.ai.models` |

---

## Task 1: Зависимости, исключения, шифрование ключей

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/ai/errors.py`
- Create: `backend/app/ai/crypto.py`
- Create: `backend/tests/test_ai_crypto.py`

- [ ] **Step 1: Failing test** — `backend/tests/test_ai_crypto.py`:
```python
from app.ai import crypto


def test_encrypt_decrypt_round_trip():
    token = crypto.encrypt("sk-secret-123")
    assert token != "sk-secret-123"  # хранится зашифрованным
    assert crypto.decrypt(token) == "sk-secret-123"


def test_encrypt_is_nondeterministic_but_decryptable():
    a = crypto.encrypt("same")
    b = crypto.encrypt("same")
    assert a != b  # Fernet добавляет IV/timestamp
    assert crypto.decrypt(a) == crypto.decrypt(b) == "same"
```

- [ ] **Step 2: Run, confirm FAIL** — `python -m pytest tests/test_ai_crypto.py -v` (ModuleNotFoundError: app.ai.crypto)

- [ ] **Step 3: Create `backend/app/ai/errors.py`:**
```python
class AINotConfigured(Exception):
    """Цель не настроена: нет модели/провайдер выключен/нет ключа."""


class AIError(Exception):
    """Ошибка вызова провайдера (сеть/таймаут/HTTP/невалидный ответ)."""
```

- [ ] **Step 4: Create `backend/app/ai/crypto.py`:**
```python
import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    # Fernet требует 32-байтный urlsafe-base64 ключ; выводим из SECRET_KEY стабильно.
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
```

- [ ] **Step 5: Deps** — в `backend/requirements.txt` добавить `cryptography>=43` и УДАЛИТЬ строку `anthropic>=0.40` (генерация уходит на новый слой). Затем `python -m pip install -r requirements.txt`.

- [ ] **Step 6: Run, confirm PASS** — `python -m pytest tests/test_ai_crypto.py -v` (2 passed)

- [ ] **Step 7: Commit**
```bash
git add backend/requirements.txt backend/app/ai/errors.py backend/app/ai/crypto.py backend/tests/test_ai_crypto.py
git commit -m "feat(ai): errors + Fernet key crypto; +cryptography -anthropic"
```

---

## Task 2: Модели AIProvider/AIModel/AIPurpose + миграция + conftest

**Files:**
- Create: `backend/app/ai/models.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_ai_models.py`
- Create: `backend/alembic/versions/d4e5f6a7b8c9_ai_provider_layer.py`

- [ ] **Step 1: Failing test** — `backend/tests/test_ai_models.py`:
```python
from app.ai.models import AIModel, AIProvider, AIPurpose


def test_provider_model_purpose_chain(db_session):
    p = AIProvider(name="aitunnel", base_url="https://api.aitunnel.ru/v1",
                   auth_style="bearer", api_key_encrypted="enc")
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    assert p.enabled is True

    m = AIModel(provider_id=p.id, model_id="anthropic/claude-3.5-sonnet", label="Claude 3.5")
    db_session.add(m); db_session.commit(); db_session.refresh(m)
    assert m.enabled is True
    assert m.input_price is None

    purpose = AIPurpose(key="proposal_generation", title="Генерация КП",
                        primary_model_id=m.id)
    db_session.add(purpose); db_session.commit(); db_session.refresh(purpose)
    assert purpose.enabled is True
    assert purpose.fallback_model_id is None
```

- [ ] **Step 2: Register in conftest** — в `backend/tests/conftest.py` после строки `from app.publiclinks import models as _publiclink_models  # noqa: F401` добавить:
```python
from app.ai import models as _ai_models  # noqa: F401
```

- [ ] **Step 3: Run, confirm FAIL** — `python -m pytest tests/test_ai_models.py -v`

- [ ] **Step 4: Create `backend/app/ai/models.py`:**
```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    base_url: Mapped[str] = mapped_column(String(500))
    auth_style: Mapped[str] = mapped_column(String(20), default="bearer")  # bearer | x_api_key
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AIModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("ai_providers.id"))
    model_id: Mapped[str] = mapped_column(String(200))
    label: Mapped[str] = mapped_column(String(200), default="")
    input_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    output_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    strengths: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AIPurpose(Base):
    __tablename__ = "ai_purposes"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    primary_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_models.id"), nullable=True
    )
    fallback_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_models.id"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

> Уникальность `(provider_id, model_id)` обеспечивается на уровне сервиса refresh (проверка перед вставкой) — отдельный constraint не добавляем, чтобы не усложнять (модели правятся только через админку).

- [ ] **Step 5: Run, confirm PASS** — `python -m pytest tests/test_ai_models.py -v`

- [ ] **Step 6: Migration** — `backend/alembic/versions/d4e5f6a7b8c9_ai_provider_layer.py`:
```python
"""ai provider layer

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-13 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: str | Sequence[str] | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'ai_providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('auth_style', sa.String(length=20), server_default=sa.text("'bearer'"), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'ai_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('label', sa.String(length=200), server_default=sa.text("''"), nullable=False),
        sa.Column('input_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('output_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('strengths', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ai_purposes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), server_default=sa.text("''"), nullable=False),
        sa.Column('description', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('primary_model_id', sa.Integer(), nullable=True),
        sa.Column('fallback_model_id', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['primary_model_id'], ['ai_models.id']),
        sa.ForeignKeyConstraint(['fallback_model_id'], ['ai_models.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    # сид целей (расширяемо — новые добавляются строкой)
    purposes = sa.table(
        'ai_purposes',
        sa.column('key', sa.String), sa.column('title', sa.String),
        sa.column('description', sa.Text), sa.column('enabled', sa.Boolean),
    )
    op.bulk_insert(purposes, [
        {'key': 'proposal_generation', 'title': 'Генерация текстов КП',
         'description': 'Маркетинговые блоки коммерческого предложения по смете и профилю.', 'enabled': True},
        {'key': 'estimate_analysis', 'title': 'Анализ сметы',
         'description': 'Подсказки по составу работ/позиций сметы.', 'enabled': True},
        {'key': 'assistant', 'title': 'Интерактивный ассистент',
         'description': 'Диалоговый помощник редактора смет (фаза 5).', 'enabled': True},
        {'key': 'router', 'title': 'Модель-роутер (советник)',
         'description': 'Подбирает оптимальную модель под каждую цель по цена-качество.', 'enabled': True},
    ])


def downgrade() -> None:
    op.drop_table('ai_purposes')
    op.drop_table('ai_models')
    op.drop_table('ai_providers')
```
Подтвердить, что `c3d4e5f6a7b8` — текущий head (нет других миграций с таким down_revision). Если нет — STOP.

- [ ] **Step 7: Commit**
```bash
git add backend/app/ai/models.py backend/tests/conftest.py backend/tests/test_ai_models.py backend/alembic/versions/d4e5f6a7b8c9_ai_provider_layer.py
git commit -m "feat(ai): AIProvider/AIModel/AIPurpose models + migration + seed purposes"
```

---

## Task 3: Pydantic-схемы

**Files:**
- Create: `backend/app/ai/schemas.py`
- Create: `backend/tests/test_ai_schemas.py`

- [ ] **Step 1: Failing test** — `backend/tests/test_ai_schemas.py`:
```python
from app.ai import schemas


def test_provider_in_defaults():
    p = schemas.ProviderIn(name="vsegpt", base_url="https://api.vsegpt.ru/v1",
                           auth_style="x_api_key", api_key="sk-or-v1")
    assert p.enabled is True


def test_provider_out_has_no_key_field():
    # ключ никогда не отдаётся наружу — только has_key
    assert "api_key" not in schemas.ProviderOut.model_fields
    assert "api_key_encrypted" not in schemas.ProviderOut.model_fields
    assert "has_key" in schemas.ProviderOut.model_fields


def test_purpose_update_partial():
    body = schemas.PurposeUpdate(primary_model_id=5)
    assert body.model_dump(exclude_unset=True) == {"primary_model_id": 5}
```

- [ ] **Step 2: Run, confirm FAIL** — `python -m pytest tests/test_ai_schemas.py -v`

- [ ] **Step 3: Create `backend/app/ai/schemas.py`:**
```python
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- providers ---
class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    base_url: str = Field(min_length=1, max_length=500)
    auth_style: Literal["bearer", "x_api_key"] = "bearer"
    api_key: str = ""  # write-only
    enabled: bool = True


class ProviderUpdate(BaseModel):
    base_url: str | None = Field(default=None, max_length=500)
    auth_style: Literal["bearer", "x_api_key"] | None = None
    api_key: str | None = None  # None/пусто = не менять ключ
    enabled: bool | None = None


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    auth_style: str
    enabled: bool
    has_key: bool  # вычисляется в роутере, ключ не отдаётся


# --- models (catalog) ---
class ModelUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    input_price: Decimal | None = None
    output_price: Decimal | None = None
    strengths: str | None = None
    enabled: bool | None = None


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    model_id: str
    label: str
    input_price: Decimal | None
    output_price: Decimal | None
    strengths: str
    enabled: bool


# --- purposes ---
class PurposeUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    primary_model_id: int | None = None
    fallback_model_id: int | None = None
    enabled: bool | None = None


class PurposeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    title: str
    description: str
    primary_model_id: int | None
    fallback_model_id: int | None
    enabled: bool


class Recommendation(BaseModel):
    purpose_key: str
    provider: str
    model_id: str
    rationale: str
```

- [ ] **Step 4: Run, confirm PASS** — `python -m pytest tests/test_ai_schemas.py -v`

- [ ] **Step 5: Commit**
```bash
git add backend/app/ai/schemas.py backend/tests/test_ai_schemas.py
git commit -m "feat(ai): pydantic schemas (write-only provider key, partial updates)"
```

---

## Task 4: HTTP-клиент провайдера

**Files:**
- Create: `backend/app/ai/client.py`
- Create: `backend/tests/test_ai_client.py`

- [ ] **Step 1: Failing test** — `backend/tests/test_ai_client.py`:
```python
import httpx
import pytest

from app.ai import client, crypto
from app.ai.errors import AIError
from app.ai.models import AIProvider


def _provider(auth_style="bearer"):
    return AIProvider(
        name="p", base_url="https://api.example.com/v1",
        auth_style=auth_style, api_key_encrypted=crypto.encrypt("sk-test-123"),
        enabled=True,
    )


def test_chat_completion_bearer_header_and_parse():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["xapi"] = request.headers.get("x-api-key")
        captured["path"] = request.url.path
        import json as _j
        captured["body"] = _j.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi there"}}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    out = client.chat_completion(_provider("bearer"), "gpt-x",
                                 [{"role": "user", "content": "q"}],
                                 max_tokens=100, json_mode=False, http=http)
    assert out == "hi there"
    assert captured["auth"] == "Bearer sk-test-123"
    assert captured["xapi"] is None
    assert captured["path"].endswith("/chat/completions")
    assert captured["body"]["model"] == "gpt-x"
    assert "response_format" not in captured["body"]


def test_chat_completion_xapikey_and_json_mode():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["xapi"] = request.headers.get("x-api-key")
        captured["auth"] = request.headers.get("authorization")
        import json as _j
        captured["body"] = _j.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client.chat_completion(_provider("x_api_key"), "m",
                           [{"role": "user", "content": "q"}],
                           max_tokens=50, json_mode=True, http=http)
    assert captured["xapi"] == "sk-test-123"
    assert captured["auth"] is None
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_chat_completion_http_error_raises_aierror():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AIError):
        client.chat_completion(_provider(), "m", [{"role": "user", "content": "q"}],
                               max_tokens=10, json_mode=False, http=http)


def test_list_models_parses_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": "gpt-x"}, {"id": "claude-y"}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    ids = client.list_models(_provider(), http=http)
    assert ids == ["gpt-x", "claude-y"]
```

- [ ] **Step 2: Run, confirm FAIL** — `python -m pytest tests/test_ai_client.py -v`

- [ ] **Step 3: Create `backend/app/ai/client.py`:**
```python
import httpx

from app.ai import crypto
from app.ai.errors import AIError
from app.ai.models import AIProvider

_TIMEOUT = 60.0


def _auth_headers(provider: AIProvider) -> dict[str, str]:
    key = crypto.decrypt(provider.api_key_encrypted) if provider.api_key_encrypted else ""
    if provider.auth_style == "x_api_key":
        return {"X-Api-Key": key}
    return {"Authorization": f"Bearer {key}"}


def _base(provider: AIProvider) -> str:
    return provider.base_url.rstrip("/")


def chat_completion(
    provider: AIProvider,
    model_id: str,
    messages: list[dict],
    *,
    max_tokens: int = 2000,
    json_mode: bool = False,
    http: httpx.Client | None = None,
) -> str:
    """POST /chat/completions к OpenAI-совместимому провайдеру. http — DI для тестов."""
    body: dict = {"model": model_id, "messages": messages, "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    owns = http is None
    http = http or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = http.post(
            f"{_base(provider)}/chat/completions",
            headers=_auth_headers(provider),
            json=body,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise AIError(f"{provider.name}: {exc}") from exc
    finally:
        if owns:
            http.close()


def list_models(provider: AIProvider, *, http: httpx.Client | None = None) -> list[str]:
    """GET /models → список id (для автоимпорта в каталог)."""
    owns = http is None
    http = http or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = http.get(
            f"{_base(provider)}/models", headers=_auth_headers(provider), timeout=_TIMEOUT
        )
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise AIError(f"{provider.name}: {exc}") from exc
    finally:
        if owns:
            http.close()
```

- [ ] **Step 4: Run, confirm PASS** — `python -m pytest tests/test_ai_client.py -v` (4 passed)

- [ ] **Step 5: Commit**
```bash
git add backend/app/ai/client.py backend/tests/test_ai_client.py
git commit -m "feat(ai): httpx provider client (chat_completion + list_models, auth styles)"
```

---

## Task 5: Диспетчер call_llm с фолбэком

**Files:**
- Create: `backend/app/ai/service.py`
- Create: `backend/tests/test_ai_service.py`

- [ ] **Step 1: Failing test** — `backend/tests/test_ai_service.py`:
```python
import json

import pytest

from app.ai import client, crypto, service
from app.ai.errors import AIError, AINotConfigured
from app.ai.models import AIModel, AIProvider, AIPurpose


def _setup(db_session, *, with_fallback=False, provider_enabled=True):
    p = AIProvider(name="p1", base_url="https://x/v1", auth_style="bearer",
                   api_key_encrypted=crypto.encrypt("k"), enabled=provider_enabled)
    db_session.add(p); db_session.commit()
    m1 = AIModel(provider_id=p.id, model_id="primary", label="P")
    m2 = AIModel(provider_id=p.id, model_id="fallback", label="F")
    db_session.add_all([m1, m2]); db_session.commit()
    purpose = AIPurpose(key="proposal_generation", title="КП",
                        primary_model_id=m1.id,
                        fallback_model_id=m2.id if with_fallback else None)
    db_session.add(purpose); db_session.commit()
    return p, m1, m2


def test_call_llm_returns_text(db_session, monkeypatch):
    _setup(db_session)
    monkeypatch.setattr(client, "chat_completion",
                        lambda prov, mid, msgs, **kw: f"answer from {mid}")
    out = service.call_llm(db_session, "proposal_generation",
                           [{"role": "user", "content": "hi"}])
    assert out == "answer from primary"


def test_call_llm_json_parses_dict(db_session, monkeypatch):
    _setup(db_session)
    monkeypatch.setattr(client, "chat_completion",
                        lambda prov, mid, msgs, **kw: json.dumps({"title": "T"}))
    out = service.call_llm(db_session, "proposal_generation",
                           [{"role": "user", "content": "hi"}],
                           json_schema={"type": "object"})
    assert out == {"title": "T"}


def test_call_llm_fallback_on_primary_error(db_session, monkeypatch):
    _setup(db_session, with_fallback=True)

    def fake(prov, mid, msgs, **kw):
        if mid == "primary":
            raise AIError("primary down")
        return "from fallback"

    monkeypatch.setattr(client, "chat_completion", fake)
    out = service.call_llm(db_session, "proposal_generation",
                           [{"role": "user", "content": "hi"}])
    assert out == "from fallback"


def test_call_llm_both_fail_raises(db_session, monkeypatch):
    _setup(db_session, with_fallback=True)
    monkeypatch.setattr(client, "chat_completion",
                        lambda *a, **k: (_ for _ in ()).throw(AIError("down")))
    with pytest.raises(AIError):
        service.call_llm(db_session, "proposal_generation",
                         [{"role": "user", "content": "hi"}])


def test_call_llm_not_configured_when_no_primary(db_session):
    db_session.add(AIPurpose(key="proposal_generation", title="КП"))
    db_session.commit()
    with pytest.raises(AINotConfigured):
        service.call_llm(db_session, "proposal_generation",
                         [{"role": "user", "content": "hi"}])


def test_call_llm_not_configured_when_provider_disabled(db_session):
    _setup(db_session, provider_enabled=False)
    with pytest.raises(AINotConfigured):
        service.call_llm(db_session, "proposal_generation",
                         [{"role": "user", "content": "hi"}])


def test_call_llm_unknown_purpose_raises(db_session):
    with pytest.raises(AINotConfigured):
        service.call_llm(db_session, "nope", [{"role": "user", "content": "hi"}])
```

- [ ] **Step 2: Run, confirm FAIL** — `python -m pytest tests/test_ai_service.py -v`

- [ ] **Step 3: Create `backend/app/ai/service.py`:**
```python
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client
from app.ai.errors import AIError, AINotConfigured
from app.ai.models import AIModel, AIProvider, AIPurpose


def _resolve(db: Session, model_id: int | None) -> tuple[AIProvider, AIModel] | None:
    """Модель по id → (провайдер, модель), если всё включено и есть ключ."""
    if model_id is None:
        return None
    model = db.get(AIModel, model_id)
    if model is None or not model.enabled:
        return None
    provider = db.get(AIProvider, model.provider_id)
    if provider is None or not provider.enabled or not provider.api_key_encrypted:
        return None
    return provider, model


def call_llm(
    db: Session,
    purpose_key: str,
    messages: list[dict],
    *,
    json_schema: dict | None = None,
    max_tokens: int = 2000,
) -> dict | str:
    """Резолв цель→модель→провайдер, вызов с фолбэком. dict если json_schema, иначе str."""
    purpose = db.scalars(
        select(AIPurpose).where(AIPurpose.key == purpose_key)
    ).first()
    if purpose is None or not purpose.enabled:
        raise AINotConfigured(f"Цель '{purpose_key}' не настроена")

    primary = _resolve(db, purpose.primary_model_id)
    if primary is None:
        raise AINotConfigured(f"Для цели '{purpose_key}' не выбрана рабочая модель")
    fallback = _resolve(db, purpose.fallback_model_id)

    json_mode = json_schema is not None
    sent = list(messages)
    if json_mode:
        sent = [
            {"role": "system",
             "content": "Верни ТОЛЬКО валидный JSON по схеме: " + json.dumps(json_schema, ensure_ascii=False)},
            *messages,
        ]

    candidates = [primary] + ([fallback] if fallback else [])
    last_err: Exception | None = None
    for provider, model in candidates:
        try:
            content = client.chat_completion(
                provider, model.model_id, sent, max_tokens=max_tokens, json_mode=json_mode
            )
            if json_mode:
                return json.loads(content)
            return content
        except (AIError, json.JSONDecodeError) as exc:
            last_err = exc
            continue
    raise AIError(f"Все модели цели '{purpose_key}' недоступны: {last_err}")
```

- [ ] **Step 4: Run, confirm PASS** — `python -m pytest tests/test_ai_service.py -v` (7 passed)

- [ ] **Step 5: Commit**
```bash
git add backend/app/ai/service.py backend/tests/test_ai_service.py
git commit -m "feat(ai): call_llm dispatcher with primary->fallback and json mode"
```

---

## Task 6: Роутер-советник

**Files:**
- Create: `backend/app/ai/router_advisor.py`
- Create: `backend/tests/test_ai_router_advisor.py`

- [ ] **Step 1: Failing test** — `backend/tests/test_ai_router_advisor.py`:
```python
from app.ai import router_advisor, service
from app.ai.models import AIModel, AIProvider, AIPurpose


def _catalog(db_session):
    p = AIProvider(name="aitunnel", base_url="https://x/v1", auth_style="bearer",
                   api_key_encrypted="enc")
    db_session.add(p); db_session.commit()
    db_session.add(AIModel(provider_id=p.id, model_id="cheap", label="Cheap",
                           input_price=10, strengths="дёшево"))
    db_session.add(AIPurpose(key="proposal_generation", title="КП",
                             description="тексты КП"))
    db_session.commit()


def test_recommend_models_builds_prompt_and_returns(db_session, monkeypatch):
    _catalog(db_session)
    seen = {}

    def fake_call(db, key, messages, **kw):
        seen["key"] = key
        seen["prompt"] = messages[-1]["content"]
        return {"recommendations": [
            {"purpose_key": "proposal_generation", "provider": "aitunnel",
             "model_id": "cheap", "rationale": "оптимально по цене"}
        ]}

    monkeypatch.setattr(service, "call_llm", fake_call)
    recs = router_advisor.recommend_models(db_session)
    assert seen["key"] == "router"          # советует модель цели "router"
    assert "cheap" in seen["prompt"]        # каталог в промпте
    assert "proposal_generation" in seen["prompt"]  # цели в промпте
    assert recs[0]["model_id"] == "cheap"
    assert recs[0]["rationale"]
```

- [ ] **Step 2: Run, confirm FAIL** — `python -m pytest tests/test_ai_router_advisor.py -v`

- [ ] **Step 3: Create `backend/app/ai/router_advisor.py`:**
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import service
from app.ai.models import AIModel, AIProvider, AIPurpose

_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "purpose_key": {"type": "string"},
                    "provider": {"type": "string"},
                    "model_id": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["purpose_key", "provider", "model_id", "rationale"],
            },
        }
    },
    "required": ["recommendations"],
}


def _catalog_text(db: Session) -> str:
    rows = db.scalars(select(AIModel).where(AIModel.enabled.is_(True))).all()
    providers = {p.id: p.name for p in db.scalars(select(AIProvider)).all()}
    lines = []
    for m in rows:
        price = f"вход {m.input_price}/выход {m.output_price} ₽/1M" if m.input_price else "цена не указана"
        lines.append(f"- {providers.get(m.provider_id, '?')}/{m.model_id}: {price}; {m.strengths or 'без заметки'}")
    return "\n".join(lines) or "(каталог пуст)"


def _purposes_text(db: Session) -> str:
    rows = db.scalars(
        select(AIPurpose).where(AIPurpose.enabled.is_(True), AIPurpose.key != "router")
    ).all()
    return "\n".join(f"- {p.key}: {p.title} — {p.description}" for p in rows) or "(нет целей)"


def recommend_models(db: Session) -> list[dict]:
    """Советник: модель цели 'router' подбирает модель под каждую цель. Не применяет."""
    prompt = (
        "Ты — инженер по подбору LLM. Доступные модели (провайдер/id: цена; сильные стороны):\n"
        + _catalog_text(db)
        + "\n\nЦели, под которые нужно подобрать модель:\n"
        + _purposes_text(db)
        + "\n\nДля каждой цели выбери оптимальную модель по соотношению цена-качество. "
        "Дай однострочное обоснование. Верни JSON с массивом recommendations."
    )
    result = service.call_llm(
        db, "router", [{"role": "user", "content": prompt}], json_schema=_SCHEMA
    )
    return result.get("recommendations", []) if isinstance(result, dict) else []
```

- [ ] **Step 4: Run, confirm PASS** — `python -m pytest tests/test_ai_router_advisor.py -v`

- [ ] **Step 5: Commit**
```bash
git add backend/app/ai/router_advisor.py backend/tests/test_ai_router_advisor.py
git commit -m "feat(ai): router advisor (recommend models per purpose, setup-time)"
```

---

## Task 7: Админ-API — провайдеры и модели

**Files:**
- Create: `backend/app/ai/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_ai_admin_providers.py`

- [ ] **Step 1: Failing test** — `backend/tests/test_ai_admin_providers.py`:
```python
import httpx

from app.ai import client
from app.auth.models import User
from app.core.security import create_access_token


def _admin(db_session):
    u = User(email="adm@x.ru", name="A", role="admin", status="active")
    db_session.add(u); db_session.commit(); return u


def _estimator(db_session):
    u = User(email="est@x.ru", name="E", role="estimator", status="active")
    db_session.add(u); db_session.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_create_provider_hides_key(client_app, db_session):
    a = _admin(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "aitunnel", "base_url": "https://api.aitunnel.ru/v1",
        "auth_style": "bearer", "api_key": "sk-aitunnel-secret"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_key"] is True
    assert "api_key" not in body and "api_key_encrypted" not in body
    # список тоже без ключа
    lst = client_app.get("/api/ai/providers", headers=_hdr(a)).json()
    assert lst[0]["has_key"] is True
    assert "api_key" not in lst[0]


def test_update_provider_keeps_key_when_omitted(client_app, db_session):
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "sk-1"}).json()["id"]
    r = client_app.put(f"/api/ai/providers/{pid}", headers=_hdr(a),
                       json={"enabled": False})  # ключ не передан
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert r.json()["has_key"] is True  # ключ сохранён


def test_provider_requires_admin(client_app, db_session):
    e = _estimator(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(e), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer", "api_key": "k"})
    assert r.status_code == 403


def test_refresh_models_imports_ids(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: ["gpt-x", "claude-y", "gpt-x"])
    r = client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2  # дубликат gpt-x не задваивается
    models = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()
    assert {m["model_id"] for m in models} == {"gpt-x", "claude-y"}
    # повторный refresh не плодит дубликаты
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    models2 = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()
    assert len(models2) == 2


def test_update_model_price(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: ["gpt-x"])
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    mid = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()[0]["id"]
    r = client_app.put(f"/api/ai/models/{mid}", headers=_hdr(a),
                       json={"input_price": "15.5", "strengths": "быстрая"})
    assert r.status_code == 200
    assert r.json()["input_price"] == "15.5000"
    assert r.json()["strengths"] == "быстрая"
```

> Примечание: фикстура называется `client_app`, а не `client`, чтобы не конфликтовать с импортом модуля `app.ai.client`. Добавь в `conftest.py` алиас (Step 2).

- [ ] **Step 2: conftest — алиас фикстуры** — в `backend/tests/conftest.py` после фикстуры `client` добавить:
```python
@pytest.fixture()
def client_app(client):
    return client
```

- [ ] **Step 3: Run, confirm FAIL** — `python -m pytest tests/test_ai_admin_providers.py -v`

- [ ] **Step 4: Create `backend/app/ai/router.py`:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client, crypto, schemas
from app.ai.models import AIModel, AIProvider, AIPurpose
from app.auth.deps import require_admin
from app.auth.models import User
from app.core.db import get_db

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _provider_out(p: AIProvider) -> schemas.ProviderOut:
    return schemas.ProviderOut(
        id=p.id, name=p.name, base_url=p.base_url, auth_style=p.auth_style,
        enabled=p.enabled, has_key=bool(p.api_key_encrypted),
    )


# --- providers ---
@router.get("/providers", response_model=list[schemas.ProviderOut])
def list_providers(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return [_provider_out(p) for p in db.scalars(select(AIProvider).order_by(AIProvider.id)).all()]


@router.post("/providers", response_model=schemas.ProviderOut, status_code=201)
def create_provider(
    body: schemas.ProviderIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    p = AIProvider(
        name=body.name, base_url=body.base_url, auth_style=body.auth_style,
        api_key_encrypted=crypto.encrypt(body.api_key) if body.api_key else "",
        enabled=body.enabled,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _provider_out(p)


@router.put("/providers/{provider_id}", response_model=schemas.ProviderOut)
def update_provider(
    provider_id: int,
    body: schemas.ProviderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    p = db.get(AIProvider, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    data = body.model_dump(exclude_unset=True)
    if "api_key" in data:
        key = data.pop("api_key")
        if key:  # пустое/None = не менять
            p.api_key_encrypted = crypto.encrypt(key)
    for field, value in data.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _provider_out(p)


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    p = db.get(AIProvider, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    db.delete(p)
    db.commit()


# --- models (catalog) ---
@router.post("/providers/{provider_id}/models/refresh")
def refresh_models(
    provider_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    p = db.get(AIProvider, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    existing = {
        m.model_id
        for m in db.scalars(select(AIModel).where(AIModel.provider_id == p.id)).all()
    }
    imported = 0
    for mid in client.list_models(p):
        if mid in existing:
            continue
        db.add(AIModel(provider_id=p.id, model_id=mid, label=mid))
        existing.add(mid)
        imported += 1
    db.commit()
    return {"imported": imported}


@router.get("/models", response_model=list[schemas.ModelOut])
def list_models(
    provider_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    q = select(AIModel).order_by(AIModel.id)
    if provider_id is not None:
        q = q.where(AIModel.provider_id == provider_id)
    return db.scalars(q).all()


@router.put("/models/{model_id}", response_model=schemas.ModelOut)
def update_model(
    model_id: int,
    body: schemas.ModelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    m = db.get(AIModel, model_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/models/{model_id}", status_code=204)
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    m = db.get(AIModel, model_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    db.delete(m)
    db.commit()
```

- [ ] **Step 5: Wire in `backend/app/main.py`** — добавить импорт `from app.ai.router import router as ai_router` и `app.include_router(ai_router)` после `public_page_router`.

- [ ] **Step 6: Run, confirm PASS** — `python -m pytest tests/test_ai_admin_providers.py -v` (5 passed)

- [ ] **Step 7: Commit**
```bash
git add backend/app/ai/router.py backend/app/main.py backend/tests/conftest.py backend/tests/test_ai_admin_providers.py
git commit -m "feat(ai): admin API — providers CRUD + models refresh/edit (write-only key)"
```

---

## Task 8: Админ-API — цели, рекомендации, проверка

**Files:**
- Modify: `backend/app/ai/router.py`
- Create: `backend/tests/test_ai_admin_purposes.py`

- [ ] **Step 1: Failing test** — `backend/tests/test_ai_admin_purposes.py`:
```python
from app.ai import router_advisor, service
from app.ai.models import AIModel, AIProvider, AIPurpose
from app.auth.models import User
from app.core.security import create_access_token


def _admin(db_session):
    u = User(email="adm@x.ru", name="A", role="admin", status="active")
    db_session.add(u); db_session.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _seed_purpose_and_model(db_session):
    db_session.add(AIPurpose(key="proposal_generation", title="КП"))
    p = AIProvider(name="p", base_url="https://x/v1", auth_style="bearer",
                   api_key_encrypted="enc")
    db_session.add(p); db_session.commit()
    m = AIModel(provider_id=p.id, model_id="m1", label="M1")
    db_session.add(m); db_session.commit()
    return m


def test_list_and_update_purpose(client_app, db_session):
    a = _admin(db_session)
    m = _seed_purpose_and_model(db_session)
    lst = client_app.get("/api/ai/purposes", headers=_hdr(a)).json()
    assert any(x["key"] == "proposal_generation" for x in lst)
    r = client_app.put("/api/ai/purposes/proposal_generation", headers=_hdr(a),
                       json={"primary_model_id": m.id})
    assert r.status_code == 200, r.text
    assert r.json()["primary_model_id"] == m.id


def test_update_unknown_purpose_404(client_app, db_session):
    a = _admin(db_session)
    assert client_app.put("/api/ai/purposes/nope", headers=_hdr(a),
                          json={"enabled": False}).status_code == 404


def test_router_recommend_returns_suggestions(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    _seed_purpose_and_model(db_session)
    monkeypatch.setattr(router_advisor, "recommend_models",
                        lambda db: [{"purpose_key": "proposal_generation",
                                     "provider": "p", "model_id": "m1", "rationale": "ok"}])
    r = client_app.post("/api/ai/router/recommend", headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json()[0]["model_id"] == "m1"


def test_purpose_test_endpoint_ok(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    _seed_purpose_and_model(db_session)
    monkeypatch.setattr(service, "call_llm", lambda *a, **k: "pong")
    r = client_app.post("/api/ai/purposes/proposal_generation/test", headers=_hdr(a))
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_purpose_test_endpoint_reports_error(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    _seed_purpose_and_model(db_session)
    from app.ai.errors import AINotConfigured
    def boom(*a, **k):
        raise AINotConfigured("нет модели")
    monkeypatch.setattr(service, "call_llm", boom)
    r = client_app.post("/api/ai/purposes/proposal_generation/test", headers=_hdr(a))
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "нет модели" in r.json()["detail"]
```

- [ ] **Step 2: Run, confirm FAIL** — `python -m pytest tests/test_ai_admin_purposes.py -v`

- [ ] **Step 3: Extend `backend/app/ai/router.py`** — добавить импорты и эндпоинты:
```python
# к существующим импортам добавить:
from app.ai import router_advisor, service
from app.ai.errors import AIError, AINotConfigured
```
```python
# --- purposes ---
@router.get("/purposes", response_model=list[schemas.PurposeOut])
def list_purposes(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return db.scalars(select(AIPurpose).order_by(AIPurpose.id)).all()


@router.put("/purposes/{key}", response_model=schemas.PurposeOut)
def update_purpose(
    key: str,
    body: schemas.PurposeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    purpose = db.scalars(select(AIPurpose).where(AIPurpose.key == key)).first()
    if purpose is None:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(purpose, field, value)
    db.commit()
    db.refresh(purpose)
    return purpose


# --- router advisor ---
@router.post("/router/recommend", response_model=list[schemas.Recommendation])
def router_recommend(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        return router_advisor.recommend_models(db)
    except AINotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# --- purpose smoke test ---
@router.post("/purposes/{key}/test")
def test_purpose(
    key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        service.call_llm(db, key, [{"role": "user", "content": "ping"}], max_tokens=16)
        return {"ok": True, "detail": ""}
    except (AINotConfigured, AIError) as exc:
        return {"ok": False, "detail": str(exc)}
```

- [ ] **Step 4: Run, confirm PASS** — `python -m pytest tests/test_ai_admin_purposes.py -v` (5 passed)

- [ ] **Step 5: Commit**
```bash
git add backend/app/ai/router.py backend/tests/test_ai_admin_purposes.py
git commit -m "feat(ai): admin API — purposes get/put, router recommend, purpose test"
```

---

## Task 9: Перенос генерации КП на call_llm

**Files:**
- Modify: `backend/app/proposals/service.py`
- Modify: `backend/app/proposals/router.py`
- Modify: `backend/tests/test_proposal_service.py`
- Modify: `backend/tests/test_proposal_api.py`

- [ ] **Step 1: Переписать тесты сервиса** — заменить `backend/tests/test_proposal_service.py` целиком:
```python
import pytest

from app.ai import service as ai_service
from app.ai.errors import AINotConfigured
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
    profile = CompanyProfile(user_id=u.id, org_name="ООО Ромашка",
                             utp=["Гарантия 5 лет"], guarantee="5 лет")
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
    fake = {"title": "Ремонт под ключ", "subtitle": "Качество",
            "pain": "Долго", "solution": "За 30 дней",
            "advantages": ["Свои бригады"], "terms": "Аванс 30%", "cta": "Звоните"}
    monkeypatch.setattr(ai_service, "call_llm", lambda db, key, messages, **kw: fake)
    result = service.generate_proposal(db_session, est, profile)
    assert result["title"] == "Ремонт под ключ"
    assert result["advantages"] == ["Свои бригады"]
    assert set(result.keys()) == {
        "title", "subtitle", "pain", "solution", "advantages", "terms", "cta"
    }


def test_generate_proposal_uses_proposal_generation_purpose(db_session, monkeypatch):
    est, profile = _estimate_with_lines(db_session)
    seen = {}

    def fake(db, key, messages, **kw):
        seen["key"] = key
        seen["json_schema"] = kw.get("json_schema")
        return {"title": "T", "subtitle": "", "pain": "", "solution": "",
                "advantages": [], "terms": "", "cta": ""}

    monkeypatch.setattr(ai_service, "call_llm", fake)
    service.generate_proposal(db_session, est, profile)
    assert seen["key"] == "proposal_generation"
    assert seen["json_schema"] is not None  # JSON-режим


def test_generate_proposal_propagates_not_configured(db_session, monkeypatch):
    est, profile = _estimate_with_lines(db_session)
    def boom(*a, **k):
        raise AINotConfigured("нет модели")
    monkeypatch.setattr(ai_service, "call_llm", boom)
    with pytest.raises(AINotConfigured):
        service.generate_proposal(db_session, est, profile)
```

- [ ] **Step 2: Run, confirm FAIL** — `python -m pytest tests/test_proposal_service.py -v`

- [ ] **Step 3: Переписать `backend/app/proposals/service.py` целиком:**
```python
from sqlalchemy.orm import Session

from app.ai import service as ai_service
from app.estimates import models as est_models
from app.estimates import service as est_service
from app.profile import models as profile_models
from app.proposals.schemas import ProposalBlocks

PURPOSE = "proposal_generation"

PROPOSAL_SCHEMA = {
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
}


def build_prompt(
    estimate: est_models.Estimate, profile: profile_models.CompanyProfile | None
) -> str:
    lines: list[str] = []
    for branch in estimate.branches:
        for section in branch.sections:
            for ln in section.lines:
                lines.append(f"- {section.name}: {ln.name} ({ln.qty} {ln.unit})")
    totals = est_service.compute_totals(estimate)

    parts: list[str] = []
    if profile is not None:
        if profile.org_name:
            parts.append(f"Компания: {profile.org_name}")
        if profile.utp:
            parts.append("УТП: " + "; ".join(profile.utp))
        if profile.cases:
            parts.append("Кейсы: " + "; ".join(profile.cases))
        if profile.guarantee:
            parts.append(f"Гарантия: {profile.guarantee}")
    profile_block = "\n".join(parts) or "(профиль исполнителя не заполнен)"

    return (
        "Ты — копирайтер строительной компании. Составь продающее коммерческое "
        "предложение по смете. Блоки на русском, в тоне делового КП "
        "(заголовок-выгода, боль клиента, решение-результат, УТП, преимущества, "
        "условия, призыв к действию).\n\n"
        f"Объект: {estimate.object_name or '(не указан)'}\n"
        f"Итоговая стоимость: {totals['total']} руб.\n\n"
        "Состав работ:\n" + ("\n".join(lines) or "(позиции не добавлены)") + "\n\n"
        "Об исполнителе:\n" + profile_block
    )


def generate_proposal(
    db: Session,
    estimate: est_models.Estimate,
    profile: profile_models.CompanyProfile | None,
) -> dict:
    prompt = build_prompt(estimate, profile)
    blocks = ai_service.call_llm(
        db, PURPOSE, [{"role": "user", "content": prompt}], json_schema=PROPOSAL_SCHEMA
    )
    return ProposalBlocks.model_validate(blocks).model_dump()
```
> Удаляются: `_call_claude`, `_OUTPUT_SCHEMA`, `ProposalAINotConfigured`, `ProposalAIError`, `MODEL`, импорты `json`/`settings`/`anthropic`. `generate_proposal` теперь принимает `db` первым аргументом.

- [ ] **Step 4: Обновить `backend/app/proposals/router.py`** — заменить обработку в `generate`:
```python
from app.ai.errors import AIError, AINotConfigured
from app.proposals import schemas, service
```
В функции `generate(...)`:
```python
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    profile = profile_service.get_profile(db, user.id)
    try:
        blocks = service.generate_proposal(db, est, profile)
    except AINotConfigured:
        raise HTTPException(status_code=503, detail="AI не настроен")
    except AIError as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка AI: {exc}")
    est.proposal = blocks
    db.commit()
    return blocks
```
> Старые `service.ProposalAINotConfigured`/`service.ProposalAIError` больше не существуют — заменены на `ai.errors`.

- [ ] **Step 5: Обновить `backend/tests/test_proposal_api.py`** — заменить мок генерации. Заменить блок импортов и тело тестов, где использовался `service._call_claude`/`service.settings.anthropic_api_key`:
```python
from app.ai import service as ai_service
from app.ai.errors import AINotConfigured
from app.auth.models import User
from app.core.security import create_access_token
from app.estimates.models import Estimate


def _user(db_session, role="estimator", email=None):
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active")
    db_session.add(u); db_session.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _estimate(db_session, owner):
    est = Estimate(owner_id=owner.id, object_name="Объект")
    db_session.add(est); db_session.commit(); db_session.refresh(est)
    return est


def test_generate_persists_blocks(client, db_session, monkeypatch):
    u = _user(db_session)
    est = _estimate(db_session, u)
    fake = {"title": "T", "subtitle": "S", "pain": "P", "solution": "Sol",
            "advantages": ["A"], "terms": "Tm", "cta": "C"}
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: fake)
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "T"
    db_session.refresh(est)
    assert est.proposal["title"] == "T"


def test_generate_503_without_config(client, db_session, monkeypatch):
    u = _user(db_session)
    est = _estimate(db_session, u)
    def boom(*a, **k):
        raise AINotConfigured("нет модели")
    monkeypatch.setattr(ai_service, "call_llm", boom)
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(u))
    assert r.status_code == 503


def test_patch_partial_and_clear(client, db_session):
    u = _user(db_session)
    est = _estimate(db_session, u)
    est.proposal = {"title": "Old", "cta": "Звоните"}
    db_session.commit()
    r = client.patch(f"/api/estimates/{est.id}/proposal", json={"title": "New"}, headers=_hdr(u))
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "New"
    assert r.json()["cta"] == "Звоните"


def test_generate_foreign_estimate_404(client, db_session, monkeypatch):
    a = _user(db_session, email="a@x.ru")
    b = _user(db_session, email="b@x.ru")
    est = _estimate(db_session, a)
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {
        "title": "", "subtitle": "", "pain": "", "solution": "",
        "advantages": [], "terms": "", "cta": ""})
    r = client.post(f"/api/estimates/{est.id}/proposal/generate", headers=_hdr(b))
    assert r.status_code == 404
```

- [ ] **Step 6: Run targeted + full** — `python -m pytest tests/test_proposal_service.py tests/test_proposal_api.py -v`, затем `python -m pytest -q` (игнорируя пред­существующий `test_auth_yandex` respx). Все, кроме него, зелёные.

- [ ] **Step 7: Commit**
```bash
git add backend/app/proposals/service.py backend/app/proposals/router.py backend/tests/test_proposal_service.py backend/tests/test_proposal_api.py
git commit -m "feat(ai): rewire proposal generation to call_llm (drop Anthropic)"
```

---

## Финальная проверка

- [ ] `python -m pytest -q` (из `backend/`) — зелено (кроме пред­существующего `test_auth_yandex`/respx).
- [ ] **Миграция на Postgres (КРИТИЧНО):** `docker compose up -d db backend` (локально) → `alembic upgrade head` → head `d4e5f6a7b8c9`, boolean-дефолты не падают.
- [ ] Линт (если настроен): `python -m ruff check app tests`.
- [ ] Финальный холистический код-ревью всей ветки.
- [ ] Push + PR (база — `main`).

## Self-Review (выполнено автором)

**Покрытие спека:** провайдеры/модели/цели (Task 2) ✓; шифрование ключей (Task 1) ✓; httpx-клиент с auth_style + list_models (Task 4) ✓; call_llm резолв+фолбэк+json (Task 5) ✓; роутер-советник (Task 6) ✓; админ-API провайдеры/модели (Task 7) + цели/recommend/test (Task 8) ✓; перенос КП на call_llm, удаление anthropic (Task 9) ✓; ключи write-only/не в ответах (Task 7) ✓; всё под require_admin (Task 7/8) ✓; миграция вручную + boolean false + сид целей (Task 2) ✓; HTTP замокан (httpx.MockTransport/monkeypatch, Task 4/5/7) ✓.

**Согласованность типов:** `chat_completion(provider, model_id, messages, *, max_tokens, json_mode, http=None)` (Task 4) ↔ вызывается в `call_llm` (Task 5) ✓. `call_llm(db, purpose_key, messages, *, json_schema, max_tokens)` (Task 5) ↔ `router_advisor` (Task 6), `proposals.service` (Task 9), `purposes/{key}/test` (Task 8) ✓. `AINotConfigured`/`AIError` из `app.ai.errors` (Task 1) — единый источник, импортируются везде ✓. Цепочка миграций `c3d4e5f6a7b8` → `d4e5f6a7b8c9` ✓. Фикстура `client_app` (Task 7) ↔ используется в Task 7/8 ✓.

**Без плейсхолдеров:** весь код приведён полностью.
