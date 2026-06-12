# SmetaApp Phase 2a — каталог и импорт прайсов (backend): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Бэкенд каталога: модели цен (5 сущностей + миграция), CRUD ценовых уровней, импорт прайсов xlsx/csv (распознавание заголовков, маппинг колонок на уровни, шаблоны поставщика, версии, дельта цен), поиск по каталогу с актуальными ценами.

**Architecture:** Всё в модуле `app/catalog/`: `models.py` (5 таблиц), `parser.py` (чтение файла → листы/строки, детект заголовка, колонки с образцами), `importer.py` (маппинг → нормализованные строки → upsert в БД с версионированием), `schemas.py`, `service.py` (поиск, актуальные цены), `router.py` (REST). Цены — `Decimal`/`Numeric(12,2)`. Деньги считаются только через Decimal, никаких float.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, openpyxl (xlsx), stdlib csv, python-multipart (загрузка файлов), pytest (фикстуры-файлы генерируются openpyxl в память).

**Working directory:** `D:\git\smeta_local_app`, ветка `phase-1-skeleton-auth` (фаза 2a продолжает её; новая ветка не нужна — PR ещё не создан). Windows/PowerShell, venv `backend\.venv`.

**Осознанные отклонения от спеки (§4):**
1. Поиск v1 — `lower(name|article) LIKE %q%` вместо tsvector+триграмм: работает на SQLite (тесты) и Postgres, каталог в десятки тысяч строк выдержит. tsvector — отложен до реальных тормозов (TODO в коде).
2. `column_mapping_template` — `JSON().with_variant(JSONB, "postgresql")`: JSONB на проде, JSON на SQLite в тестах.

**Перед началом:** поднять dev-Postgres для миграций: `docker compose -f docker-compose.dev.yml up -d db` (хост-порт **5433**). Для alembic-команд: `$env:DATABASE_URL='postgresql+psycopg://smeta:smeta@localhost:5433/smeta'`.

---

### Task 1: Зависимости + модели каталога + миграция

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/catalog/models.py`
- Modify: `backend/alembic/env.py`, `backend/tests/conftest.py` (регистрация моделей)
- Test: `backend/tests/test_catalog_models.py`

- [ ] **Step 1: Зависимости**

В `backend/requirements.txt` добавить две строки:
```
openpyxl>=3.1
python-multipart>=0.0.9
```
Установить: `.venv\Scripts\pip install -r requirements.txt` (из `backend/`).

- [ ] **Step 2: Failing test**

`backend/tests/test_catalog_models.py`:
```python
from decimal import Decimal

from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier


def test_catalog_models_roundtrip(db_session):
    level = PriceLevel(name="Закупка", sort_order=1)
    supplier = Supplier(name="Bolid")
    db_session.add_all([level, supplier])
    db_session.commit()

    price_list = PriceList(supplier_id=supplier.id, filename="bolid.xlsx", version=1)
    item = CatalogItem(supplier_id=supplier.id, name="С2000-М", article="004432")
    db_session.add_all([price_list, item])
    db_session.commit()

    price = ItemPrice(
        item_id=item.id,
        price_list_id=price_list.id,
        price_level_id=level.id,
        value=Decimal("12721.31"),
    )
    db_session.add(price)
    db_session.commit()
    db_session.refresh(price)

    assert price.value == Decimal("12721.31")
    assert item.kind == "material"
    assert item.unit == "шт"
    assert supplier.column_mapping_template is None
    assert price_list.imported_at is not None
```

- [ ] **Step 3: Run — FAIL** (`ModuleNotFoundError: app.catalog.models`)

Run: `.venv\Scripts\python -m pytest tests/test_catalog_models.py -v`

- [ ] **Step 4: Модели**

`backend/app/catalog/models.py`:
```python
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

KINDS = ("material", "work")


class PriceLevel(Base):
    __tablename__ = "price_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    sort_order: Mapped[int] = mapped_column(default=0)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    column_mapping_template: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )


class PriceList(Base):
    __tablename__ = "price_lists"
    __table_args__ = (UniqueConstraint("supplier_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    version: Mapped[int]
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("supplier_id", "article", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    article: Mapped[str] = mapped_column(String(100), default="", index=True)
    unit: Mapped[str] = mapped_column(String(20), default="шт")
    category: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(10), default="material")


class ItemPrice(Base):
    __tablename__ = "item_prices"
    __table_args__ = (UniqueConstraint("item_id", "price_list_id", "price_level_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id"), index=True)
    price_list_id: Mapped[int] = mapped_column(ForeignKey("price_lists.id"), index=True)
    price_level_id: Mapped[int] = mapped_column(ForeignKey("price_levels.id"))
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
```

Регистрация моделей: в `backend/alembic/env.py` рядом с `from app.auth import models  # noqa: F401` добавить:
```python
from app.catalog import models as catalog_models  # noqa: F401
```
В `backend/tests/conftest.py` рядом с `from app.auth import models as _models  # noqa: F401` добавить:
```python
from app.catalog import models as _catalog_models  # noqa: F401
```

- [ ] **Step 5: Run — PASS.** Возможен warning «sqlite does not support Decimal natively» — допустимо, тесты обязаны быть зелёными.

- [ ] **Step 6: Миграция**

```powershell
docker compose -f ..\docker-compose.dev.yml up -d db   # если ещё не поднят (из backend/ путь ..\)
$env:DATABASE_URL='postgresql+psycopg://smeta:smeta@localhost:5433/smeta'
.venv\Scripts\alembic revision --autogenerate -m "catalog tables"
.venv\Scripts\alembic upgrade head
```
Expected: новая ревизия в `backend/alembic/versions/` с пятью `create_table`; `upgrade head` без ошибок. Проверить глазами: уникальные констрейнты (price_levels.name, suppliers.name, (supplier_id,version), (supplier_id,article,name), (item_id,price_list_id,price_level_id)), Numeric(12,2), JSONB для column_mapping_template (autogenerate может выдать JSON — поправить руками на `postgresql.JSONB(astext_type=sa.Text())` в версии для Postgres ИЛИ оставить вариантный тип как сгенерировано, если он корректен).

- [ ] **Step 7: Полный прогон + commit**

`.venv\Scripts\python -m pytest -q` (42 passed), `.venv\Scripts\ruff check .` чисто.
```bash
git add backend/requirements.txt backend/app/catalog backend/alembic backend/tests
git commit -m "feat(catalog): модели PriceLevel/Supplier/PriceList/CatalogItem/ItemPrice + миграция"
```

---

### Task 2: CRUD ценовых уровней

**Files:**
- Create: `backend/app/catalog/schemas.py`, `backend/app/catalog/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_price_levels.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_price_levels.py`:
```python
def make_admin(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "admin@test.ru", "password": "secret123", "name": "А"},
    )
    assert resp.status_code == 201
    resp = client.post(
        "/api/auth/login", json={"email": "admin@test.ru", "password": "secret123"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_admin_creates_and_lists_levels(client):
    admin = make_admin(client)
    resp = client.post(
        "/api/price-levels", json={"name": "Закупка", "sort_order": 1}, headers=admin
    )
    assert resp.status_code == 201
    client.post("/api/price-levels", json={"name": "Розница", "sort_order": 2}, headers=admin)
    resp = client.get("/api/price-levels", headers=admin)
    assert [lvl["name"] for lvl in resp.json()] == ["Закупка", "Розница"]


def test_duplicate_level_name_409(client):
    admin = make_admin(client)
    client.post("/api/price-levels", json={"name": "Опт"}, headers=admin)
    resp = client.post("/api/price-levels", json={"name": "Опт"}, headers=admin)
    assert resp.status_code == 409


def test_rename_level(client):
    admin = make_admin(client)
    lvl = client.post("/api/price-levels", json={"name": "Опт"}, headers=admin).json()
    resp = client.patch(
        f"/api/price-levels/{lvl['id']}", json={"name": "Опт 2026"}, headers=admin
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Опт 2026"


def test_delete_level(client):
    admin = make_admin(client)
    lvl = client.post("/api/price-levels", json={"name": "Врем"}, headers=admin).json()
    assert client.delete(f"/api/price-levels/{lvl['id']}", headers=admin).status_code == 204
    assert client.get("/api/price-levels", headers=admin).json() == []


def test_non_admin_cannot_write_levels(client):
    make_admin(client)
    client.post(
        "/api/auth/register",
        json={"email": "user@test.ru", "password": "secret123", "name": "Ю"},
    )
    resp = client.post("/api/auth/login", json={"email": "user@test.ru", "password": "secret123"})
    user = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert client.post("/api/price-levels", json={"name": "X"}, headers=user).status_code == 403
```

- [ ] **Step 2: Run — FAIL** (404)

- [ ] **Step 3: Реализация**

`backend/app/catalog/schemas.py`:
```python
from pydantic import BaseModel, ConfigDict, Field


class PriceLevelIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class PriceLevelPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None


class PriceLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
```

`backend/app/catalog/router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_active, require_admin
from app.catalog.models import PriceLevel
from app.catalog.schemas import PriceLevelIn, PriceLevelOut, PriceLevelPatch
from app.core.db import get_db

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get(
    "/price-levels", response_model=list[PriceLevelOut], dependencies=[Depends(require_active)]
)
def list_price_levels(db: Session = Depends(get_db)):
    return db.scalars(select(PriceLevel).order_by(PriceLevel.sort_order, PriceLevel.id)).all()


@router.post(
    "/price-levels",
    response_model=PriceLevelOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_price_level(body: PriceLevelIn, db: Session = Depends(get_db)):
    if db.scalar(select(PriceLevel).where(PriceLevel.name == body.name)):
        raise HTTPException(status_code=409, detail="Уровень с таким именем уже есть")
    level = PriceLevel(name=body.name, sort_order=body.sort_order)
    db.add(level)
    db.commit()
    db.refresh(level)
    return level


@router.patch(
    "/price-levels/{level_id}",
    response_model=PriceLevelOut,
    dependencies=[Depends(require_admin)],
)
def update_price_level(level_id: int, body: PriceLevelPatch, db: Session = Depends(get_db)):
    level = db.get(PriceLevel, level_id)
    if level is None:
        raise HTTPException(status_code=404, detail="Уровень не найден")
    if body.name is not None:
        level.name = body.name
    if body.sort_order is not None:
        level.sort_order = body.sort_order
    db.commit()
    db.refresh(level)
    return level


@router.delete(
    "/price-levels/{level_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def delete_price_level(level_id: int, db: Session = Depends(get_db)):
    level = db.get(PriceLevel, level_id)
    if level is None:
        raise HTTPException(status_code=404, detail="Уровень не найден")
    db.delete(level)
    db.commit()
```

В `backend/app/main.py` добавить:
```python
from app.catalog.router import router as catalog_router

app.include_router(catalog_router)
```

- [ ] **Step 4: Run — PASS** (6 passed), полный прогон зелёный, ruff чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests/test_price_levels.py
git commit -m "feat(catalog): CRUD ценовых уровней (админ пишет, активные читают)"
```

---

### Task 3: API поставщиков

**Files:**
- Modify: `backend/app/catalog/schemas.py`, `backend/app/catalog/router.py`
- Test: `backend/tests/test_suppliers.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_suppliers.py`:
```python
from tests.test_price_levels import make_admin


def test_create_and_list_suppliers(client):
    admin = make_admin(client)
    resp = client.post("/api/suppliers", json={"name": "Bolid"}, headers=admin)
    assert resp.status_code == 201
    assert resp.json()["column_mapping_template"] is None
    client.post("/api/suppliers", json={"name": "Optimus"}, headers=admin)
    names = [s["name"] for s in client.get("/api/suppliers", headers=admin).json()]
    assert names == ["Bolid", "Optimus"]


def test_duplicate_supplier_409(client):
    admin = make_admin(client)
    client.post("/api/suppliers", json={"name": "Bolid"}, headers=admin)
    assert client.post("/api/suppliers", json={"name": "Bolid"}, headers=admin).status_code == 409
```

- [ ] **Step 2: Run — FAIL** (404)

- [ ] **Step 3: Реализация**

В `backend/app/catalog/schemas.py` добавить:
```python
class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    column_mapping_template: dict | None
```

В `backend/app/catalog/router.py` добавить (импорты: `Supplier`, `SupplierIn`, `SupplierOut`):
```python
@router.get(
    "/suppliers", response_model=list[SupplierOut], dependencies=[Depends(require_active)]
)
def list_suppliers(db: Session = Depends(get_db)):
    return db.scalars(select(Supplier).order_by(Supplier.name)).all()


@router.post(
    "/suppliers", response_model=SupplierOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_supplier(body: SupplierIn, db: Session = Depends(get_db)):
    if db.scalar(select(Supplier).where(Supplier.name == body.name)):
        raise HTTPException(status_code=409, detail="Поставщик уже существует")
    supplier = Supplier(name=body.name)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier
```

- [ ] **Step 4: Run — PASS**, полный прогон зелёный, ruff чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog backend/tests/test_suppliers.py
git commit -m "feat(catalog): API поставщиков (список, создание)"
```

---

### Task 4: Тестовые фикстуры-файлы (генераторы)

**Files:**
- Create: `backend/tests/catalog_files.py`

- [ ] **Step 1: Генераторы файлов** (это тестовая инфраструктура — тестов на неё нет, её используют задачи 5-9)

`backend/tests/catalog_files.py`:
```python
"""Генераторы файлов-фикстур: миниатюры реальных прайсов (Bolid, Optimus, работы)."""

import csv
import io

from openpyxl import Workbook


def make_bolid_xlsx() -> bytes:
    """Плоский прайс: заголовок в первой строке, розница + опт."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Болид"
    ws.append(["Название", "Описание", "Артикул", "Розничная_цена", "Оптовая_цена"])
    ws.append(["Сириус", "Прибор приемно-контрольный", "1-520-887", 36159.53, 33378.03])
    ws.append(["С2000-М", "Пульт контроля", "110-058-274", 12721.31, 11742.74])
    ws.append(["С2000-КДЛ", "Контроллер ДПЛС", "10-468-001", 4277.44, 3948.41])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_optimus_xlsx() -> bytes:
    """Многолистовой прайс: мусор перед заголовком, листы = категории."""
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "IP камеры"
    ws1.append(["Прайс-лист Optimus", None, None])
    ws1.append([None, None, None])
    ws1.append(["Модель", "Наименование", "Цена партнёра"])
    ws1.append(["IP-E012.1", "Видеокамера Optimus IP-E012.1", 3210.50])
    ws1.append(["IP-E014.0", "Видеокамера Optimus IP-E014.0", 5283.00])
    ws2 = wb.create_sheet("Сетевое оборудование")
    ws2.append(["Прайс-лист Optimus", None, None])
    ws2.append([None, None, None])
    ws2.append(["Модель", "Наименование", "Цена партнёра"])
    ws2.append(["U1E-8F", "Коммутатор Optimus U1E-8F", 6920.00])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_works_xlsx() -> bytes:
    """Прайс работ: имя/цена/ед.изм."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Лист1"
    ws.append(["Наименование работы", "Цена руб.", "Ед. изм."])
    ws.append(["Монтаж камеры", 3500, "шт"])
    ws.append(["Прокладка кабеля", 150, "м"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_bolid_csv() -> bytes:
    """CSV-вариант плоского прайса (cp1251 — частая кодировка выгрузок)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Название", "Артикул", "Розничная_цена", "Оптовая_цена"])
    writer.writerow(["Сириус", "1-520-887", "36159,53", "33378,03"])
    writer.writerow(["С2000-М", "110-058-274", "12721,31", "11742,74"])
    return buf.getvalue().encode("cp1251")
```

- [ ] **Step 2: Smoke-проверка** — `.venv\Scripts\python -c "from tests.catalog_files import make_bolid_xlsx; print(len(make_bolid_xlsx()))"` из `backend/` выводит число > 0. ruff чистый.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/catalog_files.py
git commit -m "test(catalog): генераторы файлов-фикстур (Bolid/Optimus/работы/csv)"
```

---

### Task 5: Парсер — чтение файла в листы/строки

**Files:**
- Create: `backend/app/catalog/parser.py`
- Test: `backend/tests/test_parser_read.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_parser_read.py`:
```python
from app.catalog.parser import load_tables
from tests.catalog_files import make_bolid_csv, make_bolid_xlsx, make_optimus_xlsx


def test_xlsx_single_sheet():
    tables = load_tables(make_bolid_xlsx(), "bolid.xlsx")
    assert list(tables.keys()) == ["Болид"]
    rows = tables["Болид"]
    assert rows[0][0] == "Название"
    assert rows[1][0] == "Сириус"
    assert len(rows) == 4


def test_xlsx_multi_sheet():
    tables = load_tables(make_optimus_xlsx(), "optimus.xlsx")
    assert list(tables.keys()) == ["IP камеры", "Сетевое оборудование"]
    assert tables["IP камеры"][3][0] == "IP-E012.1"


def test_csv_semicolon_cp1251():
    tables = load_tables(make_bolid_csv(), "bolid.csv")
    assert list(tables.keys()) == ["csv"]
    rows = tables["csv"]
    assert rows[0] == ["Название", "Артикул", "Розничная_цена", "Оптовая_цена"]
    assert rows[1][0] == "Сириус"


def test_unsupported_extension():
    import pytest

    from app.catalog.parser import UnsupportedFileError

    with pytest.raises(UnsupportedFileError):
        load_tables(b"x", "file.pdf")
```

- [ ] **Step 2: Run — FAIL** (ModuleNotFoundError)

- [ ] **Step 3: Реализация**

`backend/app/catalog/parser.py`:
```python
"""Чтение прайс-файлов: xlsx (openpyxl) и csv (auto-кодировка, auto-разделитель)."""

import csv
import io

from openpyxl import load_workbook

Cell = str | float | int | None
Rows = list[list[Cell]]


class UnsupportedFileError(Exception):
    pass


def load_tables(content: bytes, filename: str) -> dict[str, Rows]:
    """Файл -> {имя листа: строки}. Для csv единственный 'лист' с именем 'csv'."""
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return _load_xlsx(content)
    if lower.endswith(".csv"):
        return {"csv": _load_csv(content)}
    raise UnsupportedFileError(filename)


def _load_xlsx(content: bytes) -> dict[str, Rows]:
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    tables: dict[str, Rows] = {}
    for ws in wb.worksheets:
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
        tables[ws.title] = rows
    wb.close()
    return tables


def _load_csv(content: bytes) -> Rows:
    text = _decode(content)
    delimiter = ";" if text.count(";") >= text.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [list(row) for row in reader]


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")
```

Примечание: utf-8-sig первым — корректный UTF-8 почти никогда не декодируется как «случайный» cp1251 без ошибок, обратное неверно, поэтому порядок важен.

- [ ] **Step 4: Run — PASS** (4 passed), полный прогон зелёный, ruff чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog/parser.py backend/tests/test_parser_read.py
git commit -m "feat(catalog): чтение xlsx/csv в таблицы (листы, кодировки, разделители)"
```

---

### Task 6: Парсер — детект заголовка и колонки с образцами

**Files:**
- Modify: `backend/app/catalog/parser.py`
- Test: `backend/tests/test_parser_header.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_parser_header.py`:
```python
from app.catalog.parser import detect_header_row, extract_columns, load_tables
from tests.catalog_files import make_bolid_xlsx, make_optimus_xlsx


def test_header_first_row():
    rows = load_tables(make_bolid_xlsx(), "b.xlsx")["Болид"]
    assert detect_header_row(rows) == 0


def test_header_after_garbage():
    rows = load_tables(make_optimus_xlsx(), "o.xlsx")["IP камеры"]
    assert detect_header_row(rows) == 2


def test_header_empty_sheet():
    assert detect_header_row([]) == 0
    assert detect_header_row([[None, None]]) == 0


def test_extract_columns_with_samples():
    rows = load_tables(make_bolid_xlsx(), "b.xlsx")["Болид"]
    cols = extract_columns(rows, header_row=0, sample_count=2)
    assert cols[0].index == 0
    assert cols[0].header == "Название"
    assert cols[0].samples == ["Сириус", "С2000-М"]
    assert cols[3].header == "Розничная_цена"
    assert cols[3].samples == ["36159.53", "12721.31"]
```

- [ ] **Step 2: Run — FAIL** (ImportError: detect_header_row)

- [ ] **Step 3: Реализация** — добавить в `backend/app/catalog/parser.py`:

```python
from dataclasses import dataclass

HEADER_SCAN_LIMIT = 20


@dataclass
class ColumnInfo:
    index: int
    header: str
    samples: list[str]


def detect_header_row(rows: Rows, scan_limit: int = HEADER_SCAN_LIMIT) -> int:
    """Первая строка, где >=3 непустых ячеек и >=70% из них — текст. Иначе 0."""
    for i, row in enumerate(rows[:scan_limit]):
        filled = [c for c in row if c is not None and str(c).strip() != ""]
        if len(filled) < 3:
            continue
        text_cells = [c for c in filled if isinstance(c, str)]
        if len(text_cells) / len(filled) >= 0.7:
            return i
    return 0


def extract_columns(rows: Rows, header_row: int, sample_count: int = 3) -> list[ColumnInfo]:
    if header_row >= len(rows):
        return []
    header = rows[header_row]
    body = rows[header_row + 1 :]
    columns: list[ColumnInfo] = []
    for idx, cell in enumerate(header):
        title = str(cell).strip() if cell is not None else f"Колонка {idx + 1}"
        samples: list[str] = []
        for row in body:
            if len(samples) >= sample_count:
                break
            value = row[idx] if idx < len(row) else None
            if value is not None and str(value).strip() != "":
                samples.append(str(value))
        columns.append(ColumnInfo(index=idx, header=title, samples=samples))
    return columns
```

- [ ] **Step 4: Run — PASS** (4 passed), полный прогон зелёный, ruff чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog/parser.py backend/tests/test_parser_header.py
git commit -m "feat(catalog): детект строки заголовка и колонки с образцами значений"
```

---

### Task 7: Импортёр — маппинг и нормализация строк

**Files:**
- Create: `backend/app/catalog/importer.py`
- Modify: `backend/app/catalog/schemas.py` (ColumnMapping)
- Test: `backend/tests/test_importer_parse.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_importer_parse.py`:
```python
from decimal import Decimal

from app.catalog.importer import parse_rows
from app.catalog.parser import load_tables
from app.catalog.schemas import ColumnMapping
from tests.catalog_files import make_bolid_csv, make_bolid_xlsx


def test_parse_bolid_two_levels():
    rows = load_tables(make_bolid_xlsx(), "b.xlsx")["Болид"]
    mapping = ColumnMapping(name_col=0, article_col=2, price_cols={1: 3, 2: 4})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert len(parsed) == 3
    first = parsed[0]
    assert first.name == "Сириус"
    assert first.article == "1-520-887"
    assert first.prices == {1: Decimal("36159.53"), 2: Decimal("33378.03")}
    assert first.problems == []


def test_parse_comma_decimal_csv():
    rows = load_tables(make_bolid_csv(), "b.csv")["csv"]
    mapping = ColumnMapping(name_col=0, article_col=1, price_cols={1: 2})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert parsed[0].prices[1] == Decimal("36159.53")


def test_skip_empty_name_rows():
    rows = [["Имя", "Цена"], [None, 100], ["", 100], ["Товар", 50]]
    mapping = ColumnMapping(name_col=0, price_cols={1: 1})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert len(parsed) == 1
    assert parsed[0].name == "Товар"


def test_bad_price_recorded_as_problem():
    rows = [["Имя", "Цена"], ["Товар", "договорная"]]
    mapping = ColumnMapping(name_col=0, price_cols={1: 1})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert parsed[0].prices == {}
    assert "Цена" in parsed[0].problems[0] or "цена" in parsed[0].problems[0]


def test_default_category_and_unit():
    rows = [["Имя", "Цена"], ["Товар", 10]]
    mapping = ColumnMapping(name_col=0, price_cols={1: 1})
    parsed = parse_rows(rows, header_row=0, mapping=mapping, default_category="IP камеры")
    assert parsed[0].category == "IP камеры"
    assert parsed[0].unit == "шт"
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Реализация**

В `backend/app/catalog/schemas.py` добавить:
```python
class ColumnMapping(BaseModel):
    """Маппинг колонок файла: индексы колонок; price_cols: {price_level_id: column_index}."""

    name_col: int
    article_col: int | None = None
    unit_col: int | None = None
    category_col: int | None = None
    price_cols: dict[int, int] = Field(default_factory=dict)
```

`backend/app/catalog/importer.py`:
```python
"""Применение маппинга к строкам файла и нормализация значений."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.catalog.parser import Rows
from app.catalog.schemas import ColumnMapping


@dataclass
class ParsedRow:
    name: str
    article: str = ""
    unit: str = "шт"
    category: str = ""
    prices: dict[int, Decimal] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def _cell(row: list, index: int | None) -> str:
    if index is None or index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


def _parse_price(raw: str) -> Decimal:
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(",", ".")
    return Decimal(cleaned).quantize(Decimal("0.01"))


def parse_rows(
    rows: Rows,
    header_row: int,
    mapping: ColumnMapping,
    default_category: str = "",
) -> list[ParsedRow]:
    parsed: list[ParsedRow] = []
    for row in rows[header_row + 1 :]:
        name = _cell(row, mapping.name_col)
        if not name:
            continue
        item = ParsedRow(
            name=name,
            article=_cell(row, mapping.article_col),
            unit=_cell(row, mapping.unit_col) or "шт",
            category=_cell(row, mapping.category_col) or default_category,
        )
        for level_id, col in mapping.price_cols.items():
            raw = _cell(row, col)
            if not raw:
                continue
            try:
                item.prices[level_id] = _parse_price(raw)
            except InvalidOperation:
                item.problems.append(f"Цена не распознана: «{raw}» (колонка {col + 1})")
        if mapping.price_cols and not item.prices and not item.problems:
            item.problems.append("Нет ни одной цены")
        parsed.append(item)
    return parsed
```

- [ ] **Step 4: Run — PASS** (5 passed), полный прогон зелёный, ruff чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog backend/tests/test_importer_parse.py
git commit -m "feat(catalog): маппинг колонок и нормализация строк (Decimal, запятые, проблемы)"
```

---

### Task 8: Импортёр — запись в БД, версии, дельта цен

**Files:**
- Modify: `backend/app/catalog/importer.py`
- Test: `backend/tests/test_importer_db.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_importer_db.py`:
```python
from decimal import Decimal

from app.catalog.importer import ParsedRow, import_parsed
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier


def setup_base(db):
    supplier = Supplier(name="Bolid")
    level = PriceLevel(name="Розница")
    db.add_all([supplier, level])
    db.commit()
    return supplier, level


def test_first_import_creates_everything(db_session):
    supplier, level = setup_base(db_session)
    parsed = [
        ParsedRow(name="Сириус", article="1-520-887", prices={level.id: Decimal("36159.53")}),
        ParsedRow(name="С2000-М", article="110-058", prices={level.id: Decimal("12721.31")}),
    ]
    summary = import_parsed(db_session, supplier.id, "bolid.xlsx", parsed, kind="material")
    assert summary.version == 1
    assert summary.items_created == 2
    assert summary.items_updated == 0
    assert summary.prices_written == 2
    assert summary.price_changes == 0
    assert db_session.query(CatalogItem).count() == 2
    assert db_session.query(ItemPrice).count() == 2


def test_second_import_new_version_and_delta(db_session):
    supplier, level = setup_base(db_session)
    import_parsed(
        db_session,
        supplier.id,
        "v1.xlsx",
        [ParsedRow(name="Сириус", article="A1", prices={level.id: Decimal("100.00")})],
        kind="material",
    )
    summary = import_parsed(
        db_session,
        supplier.id,
        "v2.xlsx",
        [
            ParsedRow(name="Сириус", article="A1", prices={level.id: Decimal("112.00")}),
            ParsedRow(name="Новый", article="A2", prices={level.id: Decimal("50.00")}),
        ],
        kind="material",
    )
    assert summary.version == 2
    assert summary.items_created == 1
    assert summary.items_updated == 1
    assert summary.price_changes == 1  # 100 -> 112
    assert db_session.query(PriceList).count() == 2
    # история сохранена: обе цены Сириуса лежат в разных прайс-листах
    assert db_session.query(ItemPrice).count() == 3


def test_upsert_by_name_when_no_article(db_session):
    supplier, level = setup_base(db_session)
    import_parsed(
        db_session,
        supplier.id,
        "w1.xlsx",
        [ParsedRow(name="Монтаж камеры", prices={level.id: Decimal("3500")})],
        kind="work",
    )
    import_parsed(
        db_session,
        supplier.id,
        "w2.xlsx",
        [ParsedRow(name="Монтаж камеры", prices={level.id: Decimal("3700")})],
        kind="work",
    )
    items = db_session.query(CatalogItem).all()
    assert len(items) == 1
    assert items[0].kind == "work"


def test_rows_with_problems_are_skipped(db_session):
    supplier, level = setup_base(db_session)
    parsed = [
        ParsedRow(name="Норм", article="A1", prices={level.id: Decimal("10")}),
        ParsedRow(name="Битый", article="A2", problems=["Нет ни одной цены"]),
    ]
    summary = import_parsed(db_session, supplier.id, "f.xlsx", parsed, kind="material")
    assert summary.items_created == 1
    assert summary.rows_skipped == 1
```

- [ ] **Step 2: Run — FAIL** (ImportError: import_parsed)

- [ ] **Step 3: Реализация** — добавить в `backend/app/catalog/importer.py`:

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.models import CatalogItem, ItemPrice, PriceList


@dataclass
class ImportSummary:
    price_list_id: int
    version: int
    items_created: int = 0
    items_updated: int = 0
    prices_written: int = 0
    price_changes: int = 0
    rows_skipped: int = 0


def _latest_prices(db: Session, supplier_id: int) -> dict[tuple[int, int], Decimal]:
    """{(item_id, level_id): value} из последнего прайс-листа поставщика."""
    last = db.scalar(
        select(PriceList)
        .where(PriceList.supplier_id == supplier_id)
        .order_by(PriceList.version.desc())
        .limit(1)
    )
    if last is None:
        return {}
    rows = db.execute(
        select(ItemPrice.item_id, ItemPrice.price_level_id, ItemPrice.value).where(
            ItemPrice.price_list_id == last.id
        )
    ).all()
    return {(item_id, level_id): value for item_id, level_id, value in rows}


def import_parsed(
    db: Session,
    supplier_id: int,
    filename: str,
    parsed: list[ParsedRow],
    kind: str,
) -> ImportSummary:
    previous = _latest_prices(db, supplier_id)
    version = (
        db.scalar(
            select(func.max(PriceList.version)).where(PriceList.supplier_id == supplier_id)
        )
        or 0
    ) + 1
    price_list = PriceList(supplier_id=supplier_id, filename=filename, version=version)
    db.add(price_list)
    db.flush()

    summary = ImportSummary(price_list_id=price_list.id, version=version)
    for row in parsed:
        if row.problems:
            summary.rows_skipped += 1
            continue
        item = _find_item(db, supplier_id, row)
        if item is None:
            item = CatalogItem(
                supplier_id=supplier_id,
                name=row.name,
                article=row.article,
                unit=row.unit,
                category=row.category,
                kind=kind,
            )
            db.add(item)
            db.flush()
            summary.items_created += 1
        else:
            item.unit = row.unit
            item.category = row.category or item.category
            summary.items_updated += 1
        for level_id, value in row.prices.items():
            db.add(
                ItemPrice(
                    item_id=item.id,
                    price_list_id=price_list.id,
                    price_level_id=level_id,
                    value=value,
                )
            )
            summary.prices_written += 1
            old = previous.get((item.id, level_id))
            if old is not None and old != value:
                summary.price_changes += 1
    db.commit()
    return summary


def _find_item(db: Session, supplier_id: int, row: ParsedRow) -> CatalogItem | None:
    """Upsert-ключ: артикул, если он есть, иначе имя."""
    query = select(CatalogItem).where(CatalogItem.supplier_id == supplier_id)
    if row.article:
        query = query.where(CatalogItem.article == row.article)
    else:
        query = query.where(CatalogItem.article == "", CatalogItem.name == row.name)
    return db.scalar(query.limit(1))
```

- [ ] **Step 4: Run — PASS** (4 passed), полный прогон зелёный, ruff чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog/importer.py backend/tests/test_importer_db.py
git commit -m "feat(catalog): импорт в БД — версии прайс-листов, upsert позиций, дельта цен"
```

---

### Task 9: API — inspect и import (загрузка файла)

**Files:**
- Modify: `backend/app/catalog/router.py`, `backend/app/catalog/schemas.py`
- Test: `backend/tests/test_catalog_import_api.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_catalog_import_api.py`:
```python
import json

from tests.catalog_files import make_bolid_xlsx, make_optimus_xlsx
from tests.test_price_levels import make_admin


def create_level(client, admin, name):
    return client.post("/api/price-levels", json={"name": name}, headers=admin).json()["id"]


def create_supplier(client, admin, name="Bolid"):
    return client.post("/api/suppliers", json={"name": name}, headers=admin).json()["id"]


def test_inspect_returns_sheets_and_columns(client):
    admin = make_admin(client)
    resp = client.post(
        "/api/catalog/inspect",
        files={"file": ("optimus.xlsx", make_optimus_xlsx())},
        headers=admin,
    )
    assert resp.status_code == 200
    sheets = resp.json()["sheets"]
    assert [s["name"] for s in sheets] == ["IP камеры", "Сетевое оборудование"]
    cam = sheets[0]
    assert cam["header_row"] == 2
    assert cam["columns"][0]["header"] == "Модель"
    assert cam["columns"][2]["samples"] == ["3210.5", "5283"]


def test_import_bolid_end_to_end(client):
    admin = make_admin(client)
    retail = create_level(client, admin, "Розница")
    opt = create_level(client, admin, "Опт")
    supplier_id = create_supplier(client, admin)
    mapping = {"name_col": 0, "article_col": 2, "price_cols": {retail: 3, opt: 4}}
    resp = client.post(
        "/api/catalog/import",
        files={"file": ("bolid.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": str(supplier_id),
            "kind": "material",
            "sheets": json.dumps(["Болид"]),
            "mapping": json.dumps(mapping),
            "use_sheet_as_category": "false",
            "save_mapping": "true",
        },
        headers=admin,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 1
    assert body["items_created"] == 3
    assert body["prices_written"] == 6
    # шаблон маппинга сохранился у поставщика
    suppliers = client.get("/api/suppliers", headers=admin).json()
    assert suppliers[0]["column_mapping_template"]["name_col"] == 0


def test_import_optimus_sheet_as_category(client):
    admin = make_admin(client)
    partner = create_level(client, admin, "Партнёр")
    supplier_id = create_supplier(client, admin, "Optimus")
    mapping = {"name_col": 1, "article_col": 0, "price_cols": {partner: 2}}
    resp = client.post(
        "/api/catalog/import",
        files={"file": ("optimus.xlsx", make_optimus_xlsx())},
        data={
            "supplier_id": str(supplier_id),
            "kind": "material",
            "sheets": json.dumps(["IP камеры", "Сетевое оборудование"]),
            "mapping": json.dumps(mapping),
            "use_sheet_as_category": "true",
            "save_mapping": "false",
        },
        headers=admin,
    )
    assert resp.status_code == 200
    assert resp.json()["items_created"] == 3


def test_import_unknown_supplier_404(client):
    admin = make_admin(client)
    resp = client.post(
        "/api/catalog/import",
        files={"file": ("b.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": "999",
            "kind": "material",
            "sheets": json.dumps(["Болид"]),
            "mapping": json.dumps({"name_col": 0, "price_cols": {}}),
            "use_sheet_as_category": "false",
            "save_mapping": "false",
        },
        headers=admin,
    )
    assert resp.status_code == 404


def test_inspect_bad_extension_415(client):
    admin = make_admin(client)
    resp = client.post(
        "/api/catalog/inspect", files={"file": ("doc.pdf", b"%PDF")}, headers=admin
    )
    assert resp.status_code == 415
```

- [ ] **Step 2: Run — FAIL** (404)

- [ ] **Step 3: Реализация**

В `backend/app/catalog/schemas.py` добавить:
```python
class ColumnOut(BaseModel):
    index: int
    header: str
    samples: list[str]


class SheetOut(BaseModel):
    name: str
    row_count: int
    header_row: int
    columns: list[ColumnOut]


class InspectOut(BaseModel):
    sheets: list[SheetOut]


class ImportSummaryOut(BaseModel):
    price_list_id: int
    version: int
    items_created: int
    items_updated: int
    prices_written: int
    price_changes: int
    rows_skipped: int
```

В `backend/app/catalog/router.py` добавить (импорты: `import json as json_lib`, `UploadFile`, `File`, `Form`, парсер/импортёр/схемы):
```python
from fastapi import File, Form, UploadFile

from app.catalog import importer, parser
from app.catalog.schemas import (
    ColumnMapping,
    ColumnOut,
    ImportSummaryOut,
    InspectOut,
    SheetOut,
)


def _load_tables_or_415(content: bytes, filename: str) -> dict:
    try:
        return parser.load_tables(content, filename)
    except parser.UnsupportedFileError:
        raise HTTPException(status_code=415, detail="Поддерживаются только .xlsx и .csv")


@router.post("/catalog/inspect", response_model=InspectOut, dependencies=[Depends(require_admin)])
async def inspect_file(file: UploadFile = File(...)):
    tables = _load_tables_or_415(await file.read(), file.filename or "")
    sheets = []
    for name, rows in tables.items():
        header_row = parser.detect_header_row(rows)
        columns = [
            ColumnOut(index=c.index, header=c.header, samples=c.samples)
            for c in parser.extract_columns(rows, header_row)
        ]
        sheets.append(
            SheetOut(name=name, row_count=len(rows), header_row=header_row, columns=columns)
        )
    return InspectOut(sheets=sheets)


@router.post(
    "/catalog/import", response_model=ImportSummaryOut, dependencies=[Depends(require_admin)]
)
async def import_file(
    file: UploadFile = File(...),
    supplier_id: int = Form(...),
    kind: str = Form(...),
    sheets: str = Form(...),
    mapping: str = Form(...),
    use_sheet_as_category: bool = Form(False),
    save_mapping: bool = Form(False),
    db: Session = Depends(get_db),
):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    if kind not in ("material", "work"):
        raise HTTPException(status_code=422, detail="kind: material или work")
    try:
        sheet_names = json_lib.loads(sheets)
        col_mapping = ColumnMapping.model_validate(json_lib.loads(mapping))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Невалидный JSON в sheets/mapping")

    tables = _load_tables_or_415(await file.read(), file.filename or "")
    parsed: list[importer.ParsedRow] = []
    for sheet_name in sheet_names:
        if sheet_name not in tables:
            raise HTTPException(status_code=422, detail=f"Лист «{sheet_name}» не найден")
        rows = tables[sheet_name]
        header_row = parser.detect_header_row(rows)
        parsed.extend(
            importer.parse_rows(
                rows,
                header_row,
                col_mapping,
                default_category=sheet_name if use_sheet_as_category else "",
            )
        )

    summary = importer.import_parsed(
        db, supplier_id, file.filename or "import", parsed, kind=kind
    )
    if save_mapping:
        supplier.column_mapping_template = col_mapping.model_dump()
        db.commit()
    return ImportSummaryOut(**summary.__dict__)
```

- [ ] **Step 4: Run — PASS** (5 passed), полный прогон зелёный, ruff чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog backend/tests/test_catalog_import_api.py
git commit -m "feat(catalog): API inspect/import — загрузка файла, маппинг, шаблон поставщика"
```

---

### Task 10: API — поиск по каталогу, история цен, список прайс-листов

**Files:**
- Create: `backend/app/catalog/service.py`
- Modify: `backend/app/catalog/router.py`, `backend/app/catalog/schemas.py`
- Test: `backend/tests/test_catalog_search.py`

- [ ] **Step 1: Failing tests**

`backend/tests/test_catalog_search.py`:
```python
import json

from tests.catalog_files import make_bolid_xlsx
from tests.test_price_levels import make_admin


def import_bolid(client, admin):
    retail = client.post("/api/price-levels", json={"name": "Розница"}, headers=admin).json()["id"]
    supplier_id = client.post("/api/suppliers", json={"name": "Bolid"}, headers=admin).json()["id"]
    mapping = {"name_col": 0, "article_col": 2, "price_cols": {retail: 3}}
    client.post(
        "/api/catalog/import",
        files={"file": ("bolid.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": str(supplier_id),
            "kind": "material",
            "sheets": json.dumps(["Болид"]),
            "mapping": json.dumps(mapping),
            "use_sheet_as_category": "false",
            "save_mapping": "false",
        },
        headers=admin,
    )
    return retail, supplier_id


def test_search_by_name_case_insensitive(client):
    admin = make_admin(client)
    retail, _ = import_bolid(client, admin)
    resp = client.get("/api/catalog/items?q=сириус", headers=admin)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Сириус"
    assert items[0]["prices"][str(retail)] == "36159.53"


def test_search_by_article(client):
    admin = make_admin(client)
    import_bolid(client, admin)
    items = client.get("/api/catalog/items?q=110-058", headers=admin).json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "С2000-М"


def test_search_pagination_and_total(client):
    admin = make_admin(client)
    import_bolid(client, admin)
    body = client.get("/api/catalog/items?limit=2&offset=0", headers=admin).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_price_history(client):
    admin = make_admin(client)
    retail, supplier_id = import_bolid(client, admin)
    item_id = client.get("/api/catalog/items?q=сириус", headers=admin).json()["items"][0]["id"]
    history = client.get(f"/api/catalog/items/{item_id}/prices", headers=admin).json()
    assert len(history) == 1
    assert history[0]["version"] == 1
    assert history[0]["value"] == "36159.53"


def test_price_lists_by_supplier(client):
    admin = make_admin(client)
    _, supplier_id = import_bolid(client, admin)
    lists = client.get(f"/api/catalog/price-lists?supplier_id={supplier_id}", headers=admin).json()
    assert len(lists) == 1
    assert lists[0]["version"] == 1
    assert lists[0]["filename"] == "bolid.xlsx"
```

- [ ] **Step 2: Run — FAIL** (404)

- [ ] **Step 3: Реализация**

`backend/app/catalog/service.py`:
```python
"""Поиск по каталогу и выборка актуальных цен."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.models import CatalogItem, ItemPrice, PriceList

# TODO(scale): при росте каталога заменить LIKE на tsvector+pg_trgm (спека §4)


def search_items(
    db: Session,
    q: str = "",
    supplier_id: int | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CatalogItem], int]:
    query = select(CatalogItem)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            func.lower(CatalogItem.name).like(pattern)
            | func.lower(CatalogItem.article).like(pattern)
        )
    if supplier_id is not None:
        query = query.where(CatalogItem.supplier_id == supplier_id)
    if kind is not None:
        query = query.where(CatalogItem.kind == kind)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(query.order_by(CatalogItem.name).limit(limit).offset(offset)).all()
    )
    return items, total


def latest_prices_for(db: Session, item_ids: list[int]) -> dict[int, dict[int, Decimal]]:
    """{item_id: {price_level_id: value}} — цена из самого свежего прайс-листа на пару."""
    if not item_ids:
        return {}
    latest_version = (
        select(
            ItemPrice.item_id,
            ItemPrice.price_level_id,
            func.max(PriceList.version).label("max_version"),
        )
        .join(PriceList, PriceList.id == ItemPrice.price_list_id)
        .where(ItemPrice.item_id.in_(item_ids))
        .group_by(ItemPrice.item_id, ItemPrice.price_level_id)
        .subquery()
    )
    rows = db.execute(
        select(ItemPrice.item_id, ItemPrice.price_level_id, ItemPrice.value)
        .join(PriceList, PriceList.id == ItemPrice.price_list_id)
        .join(
            latest_version,
            (ItemPrice.item_id == latest_version.c.item_id)
            & (ItemPrice.price_level_id == latest_version.c.price_level_id)
            & (PriceList.version == latest_version.c.max_version),
        )
    ).all()
    result: dict[int, dict[int, Decimal]] = {}
    for item_id, level_id, value in rows:
        result.setdefault(item_id, {})[level_id] = value
    return result
```

В `backend/app/catalog/schemas.py` добавить:
```python
from decimal import Decimal


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    name: str
    article: str
    unit: str
    category: str
    kind: str
    prices: dict[int, Decimal] = {}


class ItemsPageOut(BaseModel):
    items: list[ItemOut]
    total: int


class PriceHistoryOut(BaseModel):
    price_list_id: int
    version: int
    imported_at: str
    price_level_id: int
    value: Decimal


class PriceListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    filename: str
    version: int
    imported_at: str | None = None
```
Примечание: pydantic v2 сериализует Decimal в JSON как строку — тесты ожидают `"36159.53"`. `imported_at` как str: при from_attributes datetime сериализуется ISO-строкой автоматически — если будет ошибка типа, заменить на `datetime` и импортировать.

В `backend/app/catalog/router.py` добавить:
```python
from app.catalog import service
from app.catalog.models import CatalogItem, ItemPrice, PriceList
from app.catalog.schemas import ItemOut, ItemsPageOut, PriceHistoryOut, PriceListOut


@router.get(
    "/catalog/items", response_model=ItemsPageOut, dependencies=[Depends(require_active)]
)
def list_items(
    q: str = "",
    supplier_id: int | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    items, total = service.search_items(db, q, supplier_id, kind, min(limit, 200), offset)
    prices = service.latest_prices_for(db, [i.id for i in items])
    out = [
        ItemOut(
            id=i.id,
            supplier_id=i.supplier_id,
            name=i.name,
            article=i.article,
            unit=i.unit,
            category=i.category,
            kind=i.kind,
            prices=prices.get(i.id, {}),
        )
        for i in items
    ]
    return ItemsPageOut(items=out, total=total)


@router.get(
    "/catalog/items/{item_id}/prices",
    response_model=list[PriceHistoryOut],
    dependencies=[Depends(require_active)],
)
def item_price_history(item_id: int, db: Session = Depends(get_db)):
    if db.get(CatalogItem, item_id) is None:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    rows = db.execute(
        select(ItemPrice, PriceList)
        .join(PriceList, PriceList.id == ItemPrice.price_list_id)
        .where(ItemPrice.item_id == item_id)
        .order_by(PriceList.version.desc())
    ).all()
    return [
        PriceHistoryOut(
            price_list_id=price.price_list_id,
            version=price_list.version,
            imported_at=price_list.imported_at.isoformat(),
            price_level_id=price.price_level_id,
            value=price.value,
        )
        for price, price_list in rows
    ]


@router.get(
    "/catalog/price-lists",
    response_model=list[PriceListOut],
    dependencies=[Depends(require_active)],
)
def list_price_lists(supplier_id: int | None = None, db: Session = Depends(get_db)):
    query = select(PriceList).order_by(PriceList.imported_at.desc())
    if supplier_id is not None:
        query = query.where(PriceList.supplier_id == supplier_id)
    rows = db.scalars(query).all()
    return [
        PriceListOut(
            id=pl.id,
            supplier_id=pl.supplier_id,
            filename=pl.filename,
            version=pl.version,
            imported_at=pl.imported_at.isoformat() if pl.imported_at else None,
        )
        for pl in rows
    ]
```

- [ ] **Step 4: Run — PASS** (5 passed), полный прогон зелёный, ruff чистый.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog backend/tests/test_catalog_search.py
git commit -m "feat(catalog): поиск с актуальными ценами, история цен, список прайс-листов"
```

---

### Task 11: Смоук на реальных файлах + README

**Files:**
- Create: `backend/tests/test_real_files_smoke.py`
- Modify: `README.md`

- [ ] **Step 1: Смоук-тест на реальных прайсах** (скипается, если файлов нет — в CI их нет)

`backend/tests/test_real_files_smoke.py`:
```python
"""Смоук на реальных прайсах с машины разработчика. В CI скипается."""

from pathlib import Path

import pytest

from app.catalog.parser import detect_header_row, extract_columns, load_tables

REAL_DIR = Path("D:/git/прайсы")

requires_real_files = pytest.mark.skipif(
    not REAL_DIR.exists(), reason="реальные прайсы доступны только локально"
)


@requires_real_files
def test_bolid_real_file_parses():
    content = (REAL_DIR / "bolid_price.xlsx").read_bytes()
    tables = load_tables(content, "bolid_price.xlsx")
    rows = next(iter(tables.values()))
    header = detect_header_row(rows)
    columns = extract_columns(rows, header)
    headers = [c.header for c in columns]
    assert "Название" in headers
    assert any("цена" in h.lower() for h in headers)
    assert len(rows) > 100


@requires_real_files
def test_works_real_file_parses():
    content = (REAL_DIR / "работы.xlsx").read_bytes()
    tables = load_tables(content, "работы.xlsx")
    rows = next(iter(tables.values()))
    columns = extract_columns(rows, detect_header_row(rows))
    assert columns[0].header == "Наименование работы"


@requires_real_files
def test_optimus_real_file_lists_sheets():
    files = list(REAL_DIR.glob("Price_Optimus*.xlsx"))
    if not files:
        pytest.skip("прайс Optimus не найден")
    tables = load_tables(files[0].read_bytes(), files[0].name)
    assert len(tables) > 5  # многолистовой
```

- [ ] **Step 2: Run** — локально 3 passed (или skip Optimus), `pytest -q` полный зелёный.

- [ ] **Step 3: README** — в раздел «Разработка» добавить абзац:
```markdown
### Импорт прайсов (фаза 2)

Бэкенд каталога: `POST /api/catalog/inspect` (просмотр структуры файла),
`POST /api/catalog/import` (импорт с маппингом колонок на ценовые уровни),
`GET /api/catalog/items?q=` (поиск). Перед импортом создайте ценовые уровни
(`POST /api/price-levels`) и поставщика (`POST /api/suppliers`). Полная
документация — http://localhost:8000/docs.
```

- [ ] **Step 4: Финальная проверка фазы 2a**

- `.venv\Scripts\python -m pytest -q` — все зелёные (41 + ~37 новых ≈ 78)
- `.venv\Scripts\ruff check .` — чисто
- `cd frontend; npm run build` — не сломан (фронт не трогали, но проверить)

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_real_files_smoke.py README.md
git commit -m "test(catalog): смоук на реальных прайсах + README по импорту"
```

---

## Что НЕ входит в фазу 2a (не делать)

- Фронтенд (мастер импорта, браузер каталога, страница уровней) — фаза 2b, отдельный план
- PDF-прайсы и парсинг сайтов поставщиков — спека относит к фазе 2+, отложено
- tsvector/pg_trgm поиск — отложен осознанно (LIKE достаточно, TODO в service.py)
- Клиенты и привязка уровня к клиенту — фаза 3
- Удаление/откат версий прайс-листов — YAGNI до запроса пользователя

## Self-review (выполнен при написании плана)

- Покрытие спеки §4 (модели каталога) и §5 (импорт: распознавание ✓ Task 6, выбор листов ✓ Task 9, маппинг+шаблон ✓ Task 7/9, предпросмотр — реализован как inspect (структура+образцы) + rows_skipped/problems в импорте; полноценный предпросмотр первых 20 строк уйдёт в UI фазы 2b через тот же inspect+parse, при необходимости добавим endpoint preview в 2b; версии+дельта ✓ Task 8)
- Плейсхолдеров нет, каждый шаг с полным кодом
- Согласованность типов: ColumnMapping (Task 7) используется в Task 9; ParsedRow/ImportSummary (Task 7/8) — в Task 9; search_items/latest_prices_for (Task 10) — в router Task 10; make_* фикстуры (Task 4) — в Tasks 5-10; make_admin (Task 2) переиспользуется в Tasks 3/9/10
