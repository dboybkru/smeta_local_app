# Реквизиты клиентов + DaData Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Полные реквизиты клиента (юр+физ) с автозаполнением через DaData (ключ в админке), отдельная страница «Клиенты», реквизиты в КП/экспорте.

**Architecture:** Новый `app/settings/` (зашифрованные настройки, ключ DaData) + `app/clients/dadata.py` (прокси DaData) + расширение `Client` модели/CRUD + `ClientsPage` фронта + блок «Заказчик» в экспорте.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2 + Alembic; React 19 + TS + Vite; pytest + Vitest.

Backend `D:\git\smeta_local_app\backend` (`.venv\Scripts\python.exe -m pytest`, `.venv\Scripts\ruff.exe check app/`). Frontend `D:\git\smeta_local_app\frontend`. Ветка `feat-client-requisites-dadata` (создана, спек закоммичен). Текущий head миграций: `a7b8c9d0e1f2`.

---

### Task 1: настройки приложения (app_settings) + ключ DaData

**Files:**
- Create: `backend/app/settings/__init__.py` (пустой), `backend/app/settings/models.py`, `backend/app/settings/service.py`, `backend/app/settings/router.py`
- Create: `backend/alembic/versions/b8c9d0e1f2a3_app_settings_and_client_requisites.py`
- Modify: `backend/app/main.py` (router), `backend/tests/conftest.py` (импорт моделей)
- Test: `backend/tests/test_settings.py`

- [ ] **Step 1: Падающий тест** `backend/tests/test_settings.py`

```python
from app.auth.models import User
from app.core.security import create_access_token
from app.settings import service as settings_service


def _admin(db):
    u = User(email="a@x.ru", name="A", role="admin", status="active")
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_secret_roundtrip_and_has(db_session):
    assert settings_service.has_secret(db_session, "dadata_token") is False
    settings_service.set_secret(db_session, "dadata_token", "tok-123")
    assert settings_service.has_secret(db_session, "dadata_token") is True
    assert settings_service.get_secret(db_session, "dadata_token") == "tok-123"


def test_dadata_settings_endpoints(client, db_session):
    a = _admin(db_session)
    assert client.get("/api/settings/dadata", headers=_hdr(a)).json() == {"has_token": False}
    r = client.put("/api/settings/dadata", headers=_hdr(a), json={"token": "T"})
    assert r.status_code == 200
    assert client.get("/api/settings/dadata", headers=_hdr(a)).json() == {"has_token": True}


def test_dadata_settings_admin_only(client, db_session):
    e = User(email="e@x.ru", name="E", role="estimator", status="active")
    db_session.add(e); db_session.commit()
    assert client.get("/api/settings/dadata", headers=_hdr(e)).status_code == 403
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_settings.py -q`.

- [ ] **Step 3: `__init__.py`** — создать пустой `backend/app/settings/__init__.py`.

- [ ] **Step 4: Модель** `backend/app/settings/models.py`

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
```

- [ ] **Step 5: Сервис** `backend/app/settings/service.py`

```python
from sqlalchemy.orm import Session

from app.ai import crypto
from app.settings.models import AppSetting


def set_secret(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    enc = crypto.encrypt(value) if value else ""
    if row is None:
        db.add(AppSetting(key=key, value=enc))
    else:
        row.value = enc
    db.commit()


def get_secret(db: Session, key: str) -> str:
    row = db.get(AppSetting, key)
    if row is None or not row.value:
        return ""
    return crypto.decrypt(row.value)


def has_secret(db: Session, key: str) -> bool:
    row = db.get(AppSetting, key)
    return bool(row and row.value)
```

- [ ] **Step 6: Роутер** `backend/app/settings/router.py`

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.auth.models import User
from app.core.db import get_db
from app.settings import service

router = APIRouter(prefix="/api/settings", tags=["settings"])

DADATA_KEY = "dadata_token"


class DadataIn(BaseModel):
    token: str = ""


@router.get("/dadata", dependencies=[Depends(require_admin)])
def get_dadata(db: Session = Depends(get_db)):
    return {"has_token": service.has_secret(db, DADATA_KEY)}


@router.put("/dadata", dependencies=[Depends(require_admin)])
def set_dadata(body: DadataIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if body.token.strip():
        service.set_secret(db, DADATA_KEY, body.token.strip())
    return {"has_token": service.has_secret(db, DADATA_KEY)}
```

- [ ] **Step 7: Миграция** `backend/alembic/versions/b8c9d0e1f2a3_app_settings_and_client_requisites.py`

```python
"""app_settings + client requisites

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-14 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'b8c9d0e1f2a3'
down_revision: str | Sequence[str] | None = 'a7b8c9d0e1f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLIENT_COLS = [
    "inn", "kpp", "ogrn", "type", "address", "actual_address",
    "phone", "email", "contact_person", "bank_name", "bank_account", "bik",
]


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )
    for col in _CLIENT_COLS:
        op.add_column('clients', sa.Column(col, sa.String(length=500), nullable=True))


def downgrade() -> None:
    for col in reversed(_CLIENT_COLS):
        op.drop_column('clients', col)
    op.drop_table('app_settings')
```

- [ ] **Step 8: Регистрация** — `backend/app/main.py`: импорт `from app.settings.router import router as settings_router` и `app.include_router(settings_router)`. `backend/tests/conftest.py`: добавить `from app.settings import models as _settings_models  # noqa: E402, F401` рядом с прочими модель-импортами.

- [ ] **Step 9: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_settings.py -q`. PASS.

- [ ] **Step 10: Commit** — `git add backend/app/settings backend/alembic/versions/b8c9d0e1f2a3_app_settings_and_client_requisites.py backend/app/main.py backend/tests/conftest.py backend/tests/test_settings.py && git commit -m "feat(settings): encrypted app_settings + DaData token admin endpoints"`

---

### Task 2: DaData-клиент + /clients/suggest

**Files:**
- Create: `backend/app/clients/__init__.py` (пустой), `backend/app/clients/dadata.py`
- Modify: `backend/app/estimates/router.py` (эндпоинт suggest + импорты)
- Test: `backend/tests/test_dadata.py`

- [ ] **Step 1: Падающий тест** `backend/tests/test_dadata.py`

```python
import httpx

from app.auth.models import User
from app.clients import dadata
from app.core.security import create_access_token
from app.settings import service as settings_service


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_suggest_parties_maps_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Token tok"
        return httpx.Response(200, json={"suggestions": [{
            "value": "ПАО Сбербанк",
            "data": {"inn": "7707083893", "kpp": "773601001", "ogrn": "1027700132195",
                     "name": {"short_with_opf": "ПАО Сбербанк"},
                     "address": {"value": "г Москва"},
                     "management": {"name": "Греф Г.О."}, "type": "LEGAL",
                     "state": {"status": "ACTIVE"}}}]})
    http = httpx.Client(transport=httpx.MockTransport(handler))
    out = dadata.suggest_parties("tok", "сбер", http=http)
    assert out[0]["inn"] == "7707083893"
    assert out[0]["address"] == "г Москва"
    assert out[0]["management"] == "Греф Г.О."


def test_suggest_parties_network_error_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")
    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert dadata.suggest_parties("tok", "x", http=http) == []


def test_clients_suggest_endpoint_no_token_empty(client, db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    r = client.get("/api/clients/suggest?q=сбер", headers=_hdr(u))
    assert r.status_code == 200 and r.json() == []


def test_clients_suggest_endpoint_with_token(client, db_session, monkeypatch):
    u = User(email="u2@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    settings_service.set_secret(db_session, "dadata_token", "tok")
    monkeypatch.setattr(dadata, "suggest_parties",
                        lambda token, q, **k: [{"value": "X", "inn": "1"}])
    r = client.get("/api/clients/suggest?q=сбер", headers=_hdr(u))
    assert r.json()[0]["inn"] == "1"
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_dadata.py -q`.

- [ ] **Step 3: `__init__.py`** — создать пустой `backend/app/clients/__init__.py`.

- [ ] **Step 4: DaData-клиент** `backend/app/clients/dadata.py`

```python
import httpx

_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
_TIMEOUT = 10.0


def suggest_parties(token: str, query: str, count: int = 10, *, http: httpx.Client | None = None) -> list[dict]:
    """Подсказки организаций/ИП от DaData. Best-effort: при любой ошибке → []."""
    if not token or not query.strip():
        return []
    owns = http is None
    http = http or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = http.post(
            _URL,
            headers={"Authorization": f"Token {token}", "Content-Type": "application/json",
                     "Accept": "application/json"},
            json={"query": query, "count": min(count, 20)},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        out = []
        for s in resp.json().get("suggestions", []):
            d = s.get("data", {}) or {}
            out.append({
                "value": s.get("value", ""),
                "inn": d.get("inn", ""),
                "kpp": d.get("kpp", ""),
                "ogrn": d.get("ogrn", ""),
                "name_short": (d.get("name") or {}).get("short_with_opf", ""),
                "address": (d.get("address") or {}).get("value", ""),
                "management": (d.get("management") or {}).get("name", ""),
                "type": d.get("type", ""),
                "status": (d.get("state") or {}).get("status", ""),
            })
        return out
    except (httpx.HTTPError, ValueError, KeyError):
        return []
    finally:
        if owns:
            http.close()
```

- [ ] **Step 5: Эндпоинт** — в `backend/app/estimates/router.py` добавить импорты `from app.clients import dadata` и `from app.settings import service as settings_service`, и эндпоинт:

```python
@router.get("/clients/suggest", dependencies=[Depends(require_active)])
def suggest_clients(q: str = "", db: Session = Depends(get_db)):
    token = settings_service.get_secret(db, "dadata_token")
    if not token:
        return []
    return dadata.suggest_parties(token, q)
```

- [ ] **Step 6: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_dadata.py -q`. PASS.

- [ ] **Step 7: Commit** — `git add backend/app/clients backend/app/estimates/router.py backend/tests/test_dadata.py && git commit -m "feat(clients): DaData party suggest proxy"`

---

### Task 3: Client модель + CRUD (реквизиты)

**Files:**
- Modify: `backend/app/estimates/models.py` (Client поля), `schemas.py` (ClientIn/Out/Patch), `router.py` (create расширить, PATCH+GET добавить)
- Test: `backend/tests/test_clients_crud.py`

- [ ] **Step 1: Падающий тест** `backend/tests/test_clients_crud.py`

```python
from app.auth.models import User
from app.core.security import create_access_token


def _u(db, role="estimator"):
    u = User(email=f"{role}@x.ru", name="U", role=role, status="active")
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_create_client_with_requisites(client, db_session):
    u = _u(db_session)
    r = client.post("/api/clients", headers=_hdr(u), json={
        "name": "ООО Ромашка", "inn": "7707083893", "kpp": "773601001",
        "phone": "+79990001122", "email": "a@b.ru"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["inn"] == "7707083893" and body["email"] == "a@b.ru"


def test_patch_client(client, db_session):
    u = _u(db_session)
    cid = client.post("/api/clients", headers=_hdr(u), json={"name": "К"}).json()["id"]
    r = client.patch(f"/api/clients/{cid}", headers=_hdr(u), json={"inn": "123", "address": "Москва"})
    assert r.status_code == 200, r.text
    assert r.json()["inn"] == "123" and r.json()["address"] == "Москва"


def test_get_client(client, db_session):
    u = _u(db_session)
    cid = client.post("/api/clients", headers=_hdr(u), json={"name": "К", "inn": "9"}).json()["id"]
    assert client.get(f"/api/clients/{cid}", headers=_hdr(u)).json()["inn"] == "9"


def test_viewer_cannot_create_client(client, db_session):
    v = _u(db_session, role="viewer")
    assert client.post("/api/clients", headers=_hdr(v), json={"name": "К"}).status_code == 403
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_clients_crud.py -q`.

- [ ] **Step 3: Модель** — в `backend/app/estimates/models.py`, в класс `Client` после `default_price_level_id` добавить:

```python
    inn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actual_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bik: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

- [ ] **Step 4: Схемы** — в `backend/app/estimates/schemas.py` заменить `ClientIn`/`ClientOut` и добавить `ClientPatch`:

```python
class _ClientFields(BaseModel):
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    type: str | None = None
    address: str | None = None
    actual_address: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_person: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    bik: str | None = None


class ClientIn(_ClientFields):
    name: str = Field(min_length=1, max_length=255)
    default_price_level_id: int | None = None


class ClientPatch(_ClientFields):
    name: str | None = Field(default=None, max_length=255)
    default_price_level_id: int | None = None


class ClientOut(_ClientFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    default_price_level_id: int | None
    created_at: datetime
```

(`Field`, `ConfigDict`, `datetime` уже импортированы в schemas.py.)

- [ ] **Step 5: Эндпоинты** — в `backend/app/estimates/router.py`:
  - в `create_client` заменить создание на проброс всех полей:

```python
    client = models.Client(**body.model_dump())
```
  - добавить (после create_client):

```python
@router.get("/clients/{client_id}", response_model=schemas.ClientOut,
            dependencies=[Depends(require_active)])
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.get(models.Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return client


@router.patch("/clients/{client_id}", response_model=schemas.ClientOut)
def update_client(
    client_id: int, body: schemas.ClientPatch,
    db: Session = Depends(get_db), user: User = Depends(require_active),
):
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Просмотр без права изменения")
    client = db.get(models.Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client
```
  Примечание: маршрут `GET /clients/{client_id}` не конфликтует с `GET /clients/suggest` (FastAPI: точный путь `/clients/suggest` объявлен в Task 2 — он должен матчиться; чтобы избежать перехвата `suggest` как `{client_id}`, **объяви `/clients/suggest` ВЫШE `/clients/{client_id}`** в файле, либо `{client_id}` принимает int и "suggest" не парсится в int → FastAPI вернёт 422; поэтому ЯВНО размести suggest-эндпоинт перед параметрическим).

- [ ] **Step 6: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_clients_crud.py tests/test_dadata.py -q`. PASS.

- [ ] **Step 7: Commit** — `git add backend/app/estimates && git commit -m "feat(clients): client requisites model + CRUD (create/get/patch)"`

---

### Task 4: блок «Заказчик» в экспорте

**Files:**
- Modify: `backend/app/export/context.py` (client в контекст), `templates/proposal.html`, `excel.py`
- Test: `backend/tests/test_export_excel.py` (дополнить)

- [ ] **Step 1: Падающий тест** — добавить в `backend/tests/test_export_excel.py`:

```python
def test_export_includes_client(db_session):
    from app.estimates.models import Client, Estimate, EstimateBranch
    u = User(email="cl@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    cl = Client(name="ООО Ромашка", inn="7707083893", address="г Москва")
    db_session.add(cl); db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Объект", client_id=cl.id)
    est.branches.append(EstimateBranch(name="Базовая"))
    db_session.add(est); db_session.commit(); db_session.refresh(est)
    context = ctx.build_export_context(est, level="full", public=False, db=db_session)
    assert context["client"]["name"] == "ООО Ромашка"
    assert context["client"]["inn"] == "7707083893"
    data = render_xlsx(context)
    wb = load_workbook(io.BytesIO(data))
    text = "\n".join(str(c.value) for row in wb.active.iter_rows() for c in row if c.value)
    assert "Ромашка" in text
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_export_excel.py::test_export_includes_client -q`.

- [ ] **Step 3: context.py** — в `build_export_context` (после получения `est`/перед `return`) собрать клиента и добавить в возвращаемый dict. В начале функции добавить:

```python
    client = db.get(models.Client, est.client_id) if (db is not None and est.client_id) else None
    client_out = None
    if client is not None:
        client_out = {
            "name": client.name, "inn": client.inn, "kpp": client.kpp,
            "ogrn": client.ogrn, "address": client.address,
            "phone": client.phone, "email": client.email,
            "contact_person": client.contact_person,
        }
```
  и в `return {...}` добавить ключ `"client": client_out,`.

- [ ] **Step 4: Шаблон** — в `backend/app/export/templates/proposal.html` после `<p>Объект: {{ object_name }}</p>` добавить:

```html
    {% if client %}
    <p>Заказчик: <strong>{{ client.name }}</strong>{% if client.inn %} · ИНН {{ client.inn }}{% endif %}{% if client.kpp %} · КПП {{ client.kpp }}{% endif %}{% if client.address %}<br>Адрес: {{ client.address }}{% endif %}{% if client.contact_person %}<br>Контакт: {{ client.contact_person }}{% endif %}{% if client.phone %} · {{ client.phone }}{% endif %}{% if client.email %} · {{ client.email }}{% endif %}</p>
    {% endif %}
```

- [ ] **Step 5: Excel** — в `backend/app/export/excel.py`, после `ws["A2"] = f"Объект: {context['object_name']}"` добавить:

```python
    client = context.get("client")
    if client:
        parts = [client.get("name")]
        if client.get("inn"):
            parts.append(f"ИНН {client['inn']}")
        if client.get("address"):
            parts.append(client["address"])
        ws["A3"] = "Заказчик: " + ", ".join(p for p in parts if p)
```
  (сдвиг строки A3 не ломает таблицу — она начинается с `row = 4`.)

- [ ] **Step 6: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_export_excel.py -q`. PASS. Полный backend: `.venv\Scripts\python.exe -m pytest -q` + `.venv\Scripts\ruff.exe check app/`.

- [ ] **Step 7: Commit** — `git add backend/app/export backend/tests/test_export_excel.py && git commit -m "feat(export): client (Заказчик) block in КП/Excel/PDF"`

---

### Task 5: frontend API-слой

**Files:**
- Create: `frontend/src/api/clients.ts`, `frontend/src/api/settings.ts`

- [ ] **Step 1: `frontend/src/api/clients.ts`**

```ts
import { api } from "./client";

export type Client = {
  id: number;
  name: string;
  default_price_level_id: number | null;
  inn: string | null; kpp: string | null; ogrn: string | null; type: string | null;
  address: string | null; actual_address: string | null;
  phone: string | null; email: string | null; contact_person: string | null;
  bank_name: string | null; bank_account: string | null; bik: string | null;
};

export type ClientInput = Partial<Omit<Client, "id">> & { name: string };
export type Suggestion = {
  value: string; inn: string; kpp: string; ogrn: string;
  name_short: string; address: string; management: string; type: string; status: string;
};

export const listClients = () => api<Client[]>("/clients");
export const getClient = (id: number) => api<Client>(`/clients/${id}`);
export const createClient = (body: ClientInput) =>
  api<Client>("/clients", { method: "POST", body: JSON.stringify(body) });
export const updateClient = (id: number, patch: Partial<ClientInput>) =>
  api<Client>(`/clients/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
export const suggestParties = (q: string) =>
  api<Suggestion[]>(`/clients/suggest?q=${encodeURIComponent(q)}`);
```

- [ ] **Step 2: `frontend/src/api/settings.ts`**

```ts
import { api } from "./client";

export const getDadataSettings = () => api<{ has_token: boolean }>("/settings/dadata");
export const setDadataToken = (token: string) =>
  api<{ has_token: boolean }>("/settings/dadata", { method: "PUT", body: JSON.stringify({ token }) });
```

- [ ] **Step 3: Проверка** — `npm run build`. PASS.

- [ ] **Step 4: Commit** — `git add frontend/src/api/clients.ts frontend/src/api/settings.ts && git commit -m "feat(clients): frontend api (clients + dadata suggest + settings)"`

---

### Task 6: ClientsPage + маршрут + ссылка + DaData-настройка

**Files:**
- Create: `frontend/src/pages/ClientsPage.tsx` (+ `frontend/src/pages/ClientsPage.test.tsx`)
- Modify: `frontend/src/App.tsx` (маршрут `/clients`), `frontend/src/components/AppHeader.tsx` (ссылка), `frontend/src/components/ai/ProvidersSection.tsx` или `AiConfigPage.tsx` (DaData-секция)

- [ ] **Step 1: Падающий тест** `frontend/src/pages/ClientsPage.test.tsx`

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import * as authModule from "../auth/AuthContext";
import ClientsPage from "./ClientsPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function stub() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role: "admin", status: "active" },
    loginWithPassword: vi.fn(), acceptTokens: vi.fn(), logout: vi.fn(),
  });
}
const CLIENT = { id: 1, name: "ООО Ромашка", default_price_level_id: null, inn: "7707083893",
  kpp: null, ogrn: null, type: null, address: "Москва", actual_address: null, phone: null,
  email: null, contact_person: null, bank_name: null, bank_account: null, bik: null };

describe("ClientsPage", () => {
  it("lists clients", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([CLIENT])));
    stub();
    render(<MemoryRouter><AuthProvider><ClientsPage /></AuthProvider></MemoryRouter>);
    expect(await screen.findByText("ООО Ромашка")).toBeInTheDocument();
  });

  it("creates a client via DaData autofill", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/clients/suggest")) return json([{ value: "ПАО Сбербанк", inn: "7707083893",
        kpp: "773601001", ogrn: "1", name_short: "ПАО Сбербанк", address: "Москва",
        management: "Греф", type: "LEGAL", status: "ACTIVE" }]);
      if ((init?.method ?? "GET") === "POST" && url.endsWith("/clients"))
        return json({ ...CLIENT, id: 2, name: "ПАО Сбербанк" }, 201);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    stub();
    render(<MemoryRouter><AuthProvider><ClientsPage /></AuthProvider></MemoryRouter>);
    await userEvent.click(await screen.findByText("Добавить клиента"));
    await userEvent.type(screen.getByLabelText("Поиск в DaData"), "сбер");
    await userEvent.click(await screen.findByText(/ПАО Сбербанк/));
    expect((screen.getByLabelText("ИНН") as HTMLInputElement).value).toBe("7707083893");
    await userEvent.click(screen.getByText("Сохранить"));
    const posts = f.mock.calls.filter((c) => ((c[1] as RequestInit)?.method ?? "GET") === "POST");
    expect(posts.length).toBe(1);
  });
});
```

- [ ] **Step 2: Запустить — упадёт** — `npm run test -- src/pages/ClientsPage.test.tsx`.

- [ ] **Step 3: Реализовать** `frontend/src/pages/ClientsPage.tsx`

```tsx
import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import {
  createClient, listClients, suggestParties, updateClient,
  type Client, type ClientInput, type Suggestion,
} from "../api/clients";

const FIELDS: { key: keyof ClientInput; label: string }[] = [
  { key: "inn", label: "ИНН" }, { key: "kpp", label: "КПП" }, { key: "ogrn", label: "ОГРН" },
  { key: "address", label: "Юр. адрес" }, { key: "actual_address", label: "Факт. адрес" },
  { key: "contact_person", label: "Контактное лицо" }, { key: "phone", label: "Телефон" },
  { key: "email", label: "Email" }, { key: "bank_name", label: "Банк" },
  { key: "bank_account", label: "Расчётный счёт" }, { key: "bik", label: "БИК" },
];

const EMPTY: ClientInput = { name: "" };

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [editing, setEditing] = useState<ClientInput & { id?: number } | null>(null);
  const [query, setQuery] = useState("");
  const [sugg, setSugg] = useState<Suggestion[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try { setClients(await listClients()); }
    catch (e) { setError(e instanceof Error ? e.message : "Ошибка"); }
  }
  useEffect(() => { void load(); }, []);

  useEffect(() => {
    if (!query.trim()) { setSugg([]); return; }
    const h = setTimeout(() => { void suggestParties(query).then(setSugg).catch(() => setSugg([])); }, 300);
    return () => clearTimeout(h);
  }, [query]);

  function applySuggestion(s: Suggestion) {
    setEditing((c) => ({
      ...(c ?? EMPTY),
      name: s.name_short || s.value, inn: s.inn, kpp: s.kpp, ogrn: s.ogrn,
      address: s.address, contact_person: s.management, type: s.type,
    }));
    setQuery(""); setSugg([]);
  }

  function setField(key: keyof ClientInput, value: string) {
    setEditing((c) => ({ ...(c ?? EMPTY), [key]: value }));
  }

  async function save() {
    if (!editing || !editing.name.trim()) { setError("Укажите название"); return; }
    setError("");
    try {
      const { id, ...body } = editing;
      if (id) await updateClient(id, body);
      else await createClient(body);
      setEditing(null); setQuery(""); setSugg([]);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Ошибка сохранения"); }
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <div className="mb-4 flex items-center gap-4">
          <h1 className="font-serif text-xl text-stone-900">Клиенты</h1>
          <button onClick={() => setEditing({ ...EMPTY })}
            className="rounded border border-stone-700 px-3 py-1 text-sm text-stone-700">Добавить клиента</button>
        </div>
        {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}

        {editing && (
          <div className="mb-6 rounded border border-stone-300 bg-white p-4 text-sm">
            <div className="relative mb-3 max-w-md">
              <span className="mb-1 block text-stone-600">Найти по названию или ИНН (DaData)</span>
              <input aria-label="Поиск в DaData" value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder="напр. Сбербанк или 7707083893"
                className="w-full rounded border border-stone-300 px-2 py-1" />
              {sugg.length > 0 && (
                <ul className="absolute z-10 mt-1 max-h-72 w-full overflow-auto rounded border border-stone-300 bg-white shadow">
                  {sugg.map((s, i) => (
                    <li key={i}>
                      <button type="button" onClick={() => applySuggestion(s)}
                        className="block w-full px-2 py-1 text-left hover:bg-stone-100">
                        {s.value} <span className="text-stone-400">ИНН {s.inn}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <label className="mb-2 block">
              <span className="mb-1 block text-stone-600">Название</span>
              <input aria-label="Название" value={editing.name}
                onChange={(e) => setField("name", e.target.value)}
                className="w-full max-w-md rounded border border-stone-300 px-2 py-1" />
            </label>
            <div className="grid max-w-2xl grid-cols-2 gap-2">
              {FIELDS.map(({ key, label }) => (
                <label key={key} className="block">
                  <span className="mb-1 block text-stone-600">{label}</span>
                  <input aria-label={label} value={(editing[key] as string) ?? ""}
                    onChange={(e) => setField(key, e.target.value)}
                    className="w-full rounded border border-stone-300 px-2 py-1" />
                </label>
              ))}
            </div>
            <div className="mt-3 space-x-2">
              <button onClick={() => void save()}
                className="rounded border border-stone-700 px-3 py-1 text-stone-700">Сохранить</button>
              <button onClick={() => { setEditing(null); setQuery(""); setSugg([]); }}
                className="text-stone-500">Отмена</button>
            </div>
          </div>
        )}

        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-2">Название</th><th>ИНН</th><th>Телефон</th><th>Email</th><th /></tr></thead>
          <tbody>
            {clients.map((c) => (
              <tr key={c.id} className="border-b border-stone-200">
                <td className="py-2 text-stone-900">{c.name}</td>
                <td className="text-stone-500">{c.inn || "—"}</td>
                <td className="text-stone-500">{c.phone || "—"}</td>
                <td className="text-stone-500">{c.email || "—"}</td>
                <td className="text-right">
                  <button onClick={() => setEditing({ ...c })}
                    className="rounded border border-stone-500 px-2 py-1 text-stone-600">Изменить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {clients.length === 0 && <p className="mt-3 text-stone-500">Клиентов пока нет.</p>}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Маршрут + ссылка** — `frontend/src/App.tsx`: импорт `import ClientsPage from "./pages/ClientsPage";` и `<Route path="/clients" element={<ClientsPage />} />` (внутри `RequireAuth`, рядом с `/estimates`). `frontend/src/components/AppHeader.tsx`: добавить после ссылки «Сметы» — `{canEdit && (<Link to="/clients" className="text-stone-600 hover:text-stone-900">Клиенты</Link>)}`.

- [ ] **Step 5: DaData-секция настройки** — в `frontend/src/pages/AiConfigPage.tsx` добавить компактную секцию ключа DaData (или внизу страницы). Импортировать `getDadataSettings, setDadataToken` из `../api/settings`. Добавить внутри `<main>` (после секций) блок:

```tsx
        <DadataSettings />
```
  и в конце файла (вне основного компонента) определить:

```tsx
function DadataSettings() {
  const [hasToken, setHasToken] = useState(false);
  const [token, setToken] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => { void getDadataSettings().then((s) => setHasToken(s.has_token)).catch(() => {}); }, []);
  async function save() {
    try { const s = await setDadataToken(token); setHasToken(s.has_token); setToken(""); setMsg("Сохранено"); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Ошибка"); }
  }
  return (
    <section className="mt-10">
      <h2 className="mb-2 font-serif text-lg text-stone-900">Интеграции · DaData</h2>
      <p className="mb-2 text-sm text-stone-500">Ключ для автозаполнения реквизитов клиентов. {hasToken ? "Ключ задан." : "Ключ не задан."}</p>
      <div className="flex items-end gap-2">
        <input type="password" aria-label="Ключ DaData" value={token} onChange={(e) => setToken(e.target.value)}
          placeholder="API-ключ DaData" className="rounded border border-stone-300 px-2 py-1 text-sm" />
        <button onClick={() => void save()} className="rounded border border-stone-700 px-3 py-1 text-sm text-stone-700">Сохранить</button>
        {msg && <span className="text-sm text-stone-500">{msg}</span>}
      </div>
    </section>
  );
}
```
  (Добавить `import { useEffect, useState } from "react";` если в AiConfigPage его ещё нет — там есть `useState`; добавить `useEffect`.)

- [ ] **Step 6: Запустить — пройдёт** — `npm run test -- src/pages/ClientsPage.test.tsx` (2 теста). Затем полный `npm run test`, `npm run build`, `npm run lint`.

- [ ] **Step 7: Commit** — `git add frontend/src/pages/ClientsPage.tsx frontend/src/pages/ClientsPage.test.tsx frontend/src/App.tsx frontend/src/components/AppHeader.tsx frontend/src/pages/AiConfigPage.tsx && git commit -m "feat(clients): ClientsPage with DaData autofill + route + DaData settings"`

---

## Самопроверка плана

**Покрытие спека:** app_settings+ключ DaData (Task 1); DaData-прокси+suggest (Task 2); Client реквизиты+CRUD (Task 3); блок «Заказчик» в экспорте (Task 4); api-слой (Task 5); ClientsPage+маршрут+ссылка+DaData-настройка (Task 6). Все решения покрыты.

**Плейсхолдеры:** нет.

**Согласованность:** `dadata_token` (Task 1 service/router) = `get_secret` в suggest (Task 2). `suggest_parties(token, q, http=)` (Task 2) = мок в тестах. Поля Client (Task 3 модель) = миграция (Task 1) = ClientOut/ClientInput (Task 3/5) = автозаполнение (Task 6) = export client-блок (Task 4). `Suggestion` поля (api Task 5) = маппинг DaData (Task 2). Маршрут `/clients/suggest` объявить ДО `/clients/{client_id}`. Миграция down_revision `a7b8c9d0e1f2` (текущий head). `build_export_context(..., db=)` уже принимает db (есть).
