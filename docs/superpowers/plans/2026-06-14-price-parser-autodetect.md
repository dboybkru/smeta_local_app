# Надёжный парсер прайс-листов (авто-определение) — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Импортировать прайсы разных поставщиков одним механизмом с авто-определением строки заголовка и ролей колонок по их подписям (двухстрочные шапки, пустые колонки-спейсеры, строки-категории, цена «по запросу»/у.е.).

**Architecture:** Новый модуль `catalog/detect.py` определяет раскладку каждого листа (`DetectedLayout`). `importer.parse_rows` переписывается на классификацию строк по наличию цены. `inspect` отдаёт определение фронту, `import` принимает по-листовый маппинг. Поля `manufacturer`/`price_on_request` добавляются в `CatalogItem`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, pytest (SQLite); React 19 + TS + Vite + Vitest.

**Спек:** `docs/superpowers/specs/2026-06-14-price-parser-autodetect-design.md`

**Команды (Windows):** бэкенд из `D:\git\smeta_local_app\backend`:
- тесты: `./.venv/Scripts/python.exe -m pytest -q`
- линт: `./.venv/Scripts/ruff.exe check app/`
Фронтенд из `frontend`: `npm run test`, `npm run build`, `npm run lint`.

---

## Структура файлов

**Backend**
- Создать: `app/catalog/detect.py` — `PriceColumn`, `DetectedLayout`, `detect_layout(rows)`.
- Изменить: `app/catalog/models.py` — `CatalogItem.manufacturer`, `CatalogItem.price_on_request`.
- Создать: `alembic/versions/d1e2f3a4b5c6_catalog_manufacturer_price_on_request.py`.
- Изменить: `app/catalog/schemas.py` — `ColumnMapping` (+`manufacturer_col`, `header_row`, `data_start_row`, `on_request_cols`), `PriceColumnOut`, `DetectedLayoutOut`, `SheetOut.detected`, `ItemOut` (+`manufacturer`, `price_on_request`), `ImportSheetMapping`.
- Изменить: `app/catalog/importer.py` — `ParsedRow` (+`manufacturer`, `price_on_request`), `parse_rows` (переписать), `import_parsed` (писать новые поля).
- Изменить: `app/catalog/router.py` — `inspect` отдаёт `detected`; `import` принимает по-листовый маппинг; `ItemOut` маппинг.
- Создать: `tests/fixtures/pricelists.py` — урезанные `Rows` всех форматов.
- Создать: `tests/test_detect.py`, `tests/test_import_formats.py`. Изменить: `tests/test_importer.py` (под новую сигнатуру `parse_rows`).

**Frontend**
- Изменить: `src/api/catalog.ts` — типы `ColumnMapping`, `PriceColumn`, `DetectedLayout`, `Sheet.detected`, `CatalogItem` (+поля), `importFile` (по-листовый payload).
- Изменить: `src/components/ColumnMapper.tsx` — поле «Производитель»; привязка найденных ценовых колонок к уровням с автоподсказкой.
- Изменить: `src/pages/ImportPage.tsx` — предзаполнение из `detected` по каждому листу, по-листовый payload.
- Изменить: `src/pages/CatalogPage.tsx` — показ `manufacturer` и бейджа «уточнить стоимость».

---

## Task 1: Модель — manufacturer + price_on_request + миграция

**Files:**
- Modify: `backend/app/catalog/models.py:56-77`
- Create: `backend/alembic/versions/d1e2f3a4b5c6_catalog_manufacturer_price_on_request.py`
- Test: `backend/tests/test_catalog_models.py` (создать)

- [ ] **Step 1: Write the failing test**

Создать `backend/tests/test_catalog_models.py`:

```python
from app.catalog.models import CatalogItem, Supplier


def test_catalog_item_new_fields_defaults(db_session):
    sup = Supplier(name="S"); db_session.add(sup); db_session.commit()
    it = CatalogItem(supplier_id=sup.id, name="Камера")
    db_session.add(it); db_session.commit(); db_session.refresh(it)
    assert it.manufacturer is None
    assert it.price_on_request is False


def test_catalog_item_set_new_fields(db_session):
    sup = Supplier(name="S2"); db_session.add(sup); db_session.commit()
    it = CatalogItem(supplier_id=sup.id, name="Камера", manufacturer="Optimus",
                     price_on_request=True)
    db_session.add(it); db_session.commit(); db_session.refresh(it)
    assert it.manufacturer == "Optimus"
    assert it.price_on_request is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_catalog_models.py -q`
Expected: FAIL — `TypeError: 'manufacturer' is an invalid keyword argument` / `AttributeError`.

- [ ] **Step 3: Add the columns**

В `backend/app/catalog/models.py`, в классе `CatalogItem` после `characteristics_raw` (строка 76) добавить:

```python
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price_on_request: Mapped[bool] = mapped_column(default=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_catalog_models.py -q`
Expected: PASS (conftest создаёт схему через `create_all`, новые колонки появятся).

- [ ] **Step 5: Write the Alembic migration**

Создать `backend/alembic/versions/d1e2f3a4b5c6_catalog_manufacturer_price_on_request.py`:

```python
"""catalog manufacturer + price_on_request

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-06-14

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "catalog_items",
        sa.Column(
            "price_on_request",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("catalog_items", "price_on_request")
    op.drop_column("catalog_items", "manufacturer")
```

- [ ] **Step 6: Verify migration head is linear**

Run: `./.venv/Scripts/python.exe -m alembic heads`
Expected: единственный head `d1e2f3a4b5c6`.
(Если alembic требует БД и падает на этом — пропустить, проверка цепочки делается ревью down_revision=`c9d0e1f2a3b4`.)

- [ ] **Step 7: Commit**

```bash
git add backend/app/catalog/models.py backend/alembic/versions/d1e2f3a4b5c6_catalog_manufacturer_price_on_request.py backend/tests/test_catalog_models.py
git commit -m "feat(catalog): поля manufacturer и price_on_request + миграция"
```

---

## Task 2: Фикстуры форматов + detect_layout (одностишные шапки, роли)

**Files:**
- Create: `backend/tests/fixtures/__init__.py` (пустой), `backend/tests/fixtures/pricelists.py`
- Create: `backend/app/catalog/detect.py`
- Test: `backend/tests/test_detect.py`

- [ ] **Step 1: Create fixtures module**

Создать `backend/tests/fixtures/__init__.py` (пустой файл).

Создать `backend/tests/fixtures/pricelists.py` (урезанные реальные раскладки; `None` = пустая ячейка):

```python
"""Урезанные раскладки реальных прайсов для тестов detect/parse."""

# bolid_price.xlsx — плоский, шапка в строке 1, Код и Артикул, 2 цены.
BOLID = [
    ["Название", "Описание", "Код", "Артикул", "Наличие", "Розничная_цена",
     "Оптовая_цена", "URL"],
    ["Сириус", "Прибор ППК", "303232", "1-520-887-052", "В наличии", "36159.53",
     "33378.03", "https://x"],
    ["С2000-М", "Пульт", "004432", "110-058-274", "В наличии", "12721.31",
     "11742.74", "https://x"],
]

# работы.xlsx — работы, шапка в строке 1, 1 цена, ед.изм.
RABOTY = [
    ["Наименование работы", "Цена руб.", "Ед. изм."],
    ["Прокладка кабеля", "150", "м"],
    ["Монтаж камеры", "3500", "шт"],
]

# Прайс-лист Контроль доступа.xlsx — двухстрочная шапка (строки 2+3),
# колонка Производитель, нет артикула, цены "звоните", строки-категории.
KONTROL = [
    ["Прайс-лист: Контроль доступа", None, None, None, None, None, None],
    ["№", "Производитель", "Наименование", "Краткая характеристика", "Цены руб.",
     None, None],
    [None, None, None, None, "1", "2", "3"],
    ["1", "Контроль доступа", None, None, None, None, None],          # категория
    ["1.1.1", "Интегрированная система", None, None, None, None, None],  # категория
    ["1", "Parsec", "CNC-02-IP", "Шлюз объединяет", "24864", "24864", "звоните"],
    ["2", "Parsec", "NMI-08", "Зонный расширитель", "3600", "3600", "звоните"],
]

# pricetin.xlsx — пустая колонка A, двухстрочная шапка (5+6), ед.изм в "руб./шт",
# строки-категории, Код (без Артикула).
PRICETIN = [
    [None, "ПРАЙС-ЛИСТ № 1", None, None, None, None, None, None, None, None],
    [None, "Действителен с 17.04", None, None, None, None, None, None, None, None],
    [None, "Средства охраны", None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None, None, None],
    [None, "№", "Код", "Наименование", "Описание", "Производитель",
     "Вал./   Ед. изм.", "Цены", None, None],
    [None, None, None, None, None, None, None, "1", "2", "3"],
    [None, "1", None, "Извещатели охранные", None, None, None, None, None, None],  # категория
    [None, None, "319298", "DD-01", "Датчик двери", "CARDDEX", "руб./шт",
     "230", "230", "230"],
    [None, None, "212271", "CM-800", "Станция", "Commax", "руб./шт",
     "2109.8", "2004.31", "1898.82"],
]

# Optimus IP камеры — шапка в строке 6, пустая колонка C, цены E..I.
OPTIMUS_IPK = [
    [None, None, None, None, None, None, None, None, None, None, None, "На главную"],
    [None] * 12,
    [None] * 12,
    ["https://clck", None, None, None, None, None, None, None, None, None, None, None],
    [None] * 12,
    ["Наименование", "Фото", None, "Краткие характеристики", "РОЗН.", "ИНСТ.",
     "ОПТ.", "КР.ОПТ.", "ПАРТ.", "Коммент.", "Код", "Ссылка"],
    [None, None, None, "Видеокамеры по типу", None, None, None, None, None, None,
     None, None],  # категория
    ["Камера Optimus 1", None, "4 Мп, 2.8мм", "1/3 CMOS", "5835", "4960", "3905.58",
     "3829", "3513", None, "B0000020936", "ссылка"],
]

# Optimus Сетевое оборудование — шапка в строке 6, БЕЗ пустой колонки C (сдвиг),
# характеристики=C, цены D..H.
OPTIMUS_NET = [
    [None, None, None, None, None, None, None, None, None, None, None],
    [None] * 11,
    [None] * 11,
    [None] * 11,
    [None] * 11,
    ["Наименование", "Фото", "Краткие характеристики", "РОЗН.", "ИНСТ.", "ОПТ.",
     "КР.ОПТ.", "ПАРТ.", "Коммент.", "Код", "Ссылка"],
    ["Коммутатор U1IC", None, "8 портов", "3034", "2579", "2030.82", "1991", "1827",
     "Аналог", "B0000019119", "ссылка"],
]

# Аккумуляторы Optimus — цены в у.е. (шапка в строке 4).
AKKUM = [
    [None] * 11,
    [None] * 11,
    [None] * 11,
    ["Наименование", "Фото", "Краткие характеристики", "РОЗН. у.е.", "ИНСТ. у.е.",
     "ОПТ. у.е.", "КР.ОПТ. у.е.", "ПАРТ. у.е.", "Коммент.", "Код", "Ссылка"],
    ["Аккумулятор 7Ач", None, "12В 7Ач", "10.5", "9.5", "8.5", "8", "7.5", None,
     "B0000030000", "ссылка"],
]
```

- [ ] **Step 2: Write failing tests for single-row detection**

Создать `backend/tests/test_detect.py`:

```python
from app.catalog.detect import detect_layout
from tests.fixtures import pricelists as P


def test_detect_bolid_flat():
    d = detect_layout(P.BOLID)
    assert d is not None
    assert d.header_row == 0
    assert d.data_start_row == 1
    assert d.name_col == 0
    assert d.chars_col == 1          # "Описание"
    assert d.article_col == 3        # "Артикул" приоритетнее "Код"
    labels = {p.index for p in d.price_columns}
    assert labels == {5, 6}          # Розничная_цена, Оптовая_цена


def test_detect_raboty():
    d = detect_layout(P.RABOTY)
    assert d.header_row == 0
    assert d.name_col == 0
    assert d.unit_col == 2
    assert [p.index for p in d.price_columns] == [1]


def test_detect_optimus_ipk_header_row_6_with_spacer():
    d = detect_layout(P.OPTIMUS_IPK)
    assert d.header_row == 5
    assert d.data_start_row == 6
    assert d.name_col == 0
    assert d.chars_col == 3
    assert d.article_col == 10
    assert [p.index for p in d.price_columns] == [4, 5, 6, 7, 8]


def test_detect_optimus_net_shifted():
    d = detect_layout(P.OPTIMUS_NET)
    assert d.header_row == 5
    assert d.chars_col == 2          # сдвиг: характеристики в колонке C(2)
    assert [p.index for p in d.price_columns] == [3, 4, 5, 6, 7]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_detect.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.catalog.detect'`.

- [ ] **Step 4: Implement detect.py (single-row layouts)**

Создать `backend/app/catalog/detect.py`:

```python
"""Авто-определение раскладки прайс-листа по подписям колонок."""

from dataclasses import dataclass, field

from app.catalog.parser import Rows

SCAN_LIMIT = 20

# Роли по приоритету. Внутри роли — синонимы по убыванию точности.
ROLE_SYNONYMS: dict[str, list[str]] = {
    "name": ["наименование работы", "наименование", "название", "товар"],
    "article": ["артикул", "код товара", "код"],
    "chars": ["краткая характеристика", "краткие характеристики",
              "характеристики", "характеристика", "описание"],
    "unit": ["ед. изм", "ед.изм", "вал./ед. изм", "единица", "ед изм"],
    "manufacturer": ["производитель", "бренд", "вендор"],
}
PRICE_WORDS = ["розничная", "розн", "оптовая", "опт", "кр.опт", "кр опт",
               "парт", "инст", "цена", "стоимость"]
GENERIC_PRICE = {"цены", "цены руб", "цены, руб", "цена руб"}


@dataclass
class PriceColumn:
    index: int
    label: str
    sample: str = ""
    on_request: bool = False


@dataclass
class DetectedLayout:
    header_row: int
    data_start_row: int
    name_col: int | None = None
    article_col: int | None = None
    chars_col: int | None = None
    unit_col: int | None = None
    manufacturer_col: int | None = None
    price_columns: list[PriceColumn] = field(default_factory=list)
    confidence: float = 0.0


def _norm(cell: object) -> str:
    if cell is None:
        return ""
    s = str(cell).strip().lower().replace("ё", "е")
    s = " ".join(s.split())
    return s.rstrip(".:")


def _is_price_word(norm: str) -> bool:
    return any(w in norm for w in PRICE_WORDS)


def _on_request_label(norm: str) -> bool:
    return any(t in norm for t in ("у.е", "у. е", "усл", "y.e"))


def _match_role(norm: str) -> tuple[str, int] | None:
    for role, syns in ROLE_SYNONYMS.items():
        for rank, s in enumerate(syns):
            if s in norm:
                return role, rank
    return None


def _score_row(row: list) -> int:
    """Сколько ячеек строки похожи на заголовки (роли или ценовые)."""
    score = 0
    has_name = has_price = False
    for cell in row:
        norm = _norm(cell)
        if not norm:
            continue
        m = _match_role(norm)
        if m:
            score += 1
            if m[0] == "name":
                has_name = True
        elif _is_price_word(norm) or norm in GENERIC_PRICE:
            score += 1
            has_price = True
    return score if (has_name and has_price) else 0


def _find_header_row(rows: Rows, scan_limit: int) -> int | None:
    best_row, best_score = None, 0
    for i, row in enumerate(rows[:scan_limit]):
        s = _score_row(row)
        if s > best_score:
            best_row, best_score = i, s
    return best_row


def _assign_roles(header: list) -> dict[str, int]:
    roles: dict[str, tuple[int, int]] = {}  # role -> (col, rank)
    for col, cell in enumerate(header):
        norm = _norm(cell)
        if not norm:
            continue
        m = _match_role(norm)
        if m is None:
            continue
        role, rank = m
        prev = roles.get(role)
        if prev is None or rank < prev[1]:
            roles[role] = (col, rank)
    return {role: col for role, (col, _rank) in roles.items()}


def _sample(rows: Rows, data_start: int, col: int) -> str:
    for row in rows[data_start:data_start + 5]:
        if col < len(row) and row[col] is not None and str(row[col]).strip():
            return str(row[col]).strip()
    return ""


def detect_layout(rows: Rows, scan_limit: int = SCAN_LIMIT) -> DetectedLayout | None:
    header_row = _find_header_row(rows, scan_limit)
    if header_row is None:
        return None
    header = rows[header_row]
    roles = _assign_roles(header)
    data_start = header_row + 1
    price_columns = _detect_price_columns(rows, header_row)
    for pc in price_columns:
        pc.sample = _sample(rows, data_start if not _is_two_row(rows, header_row)
                            else header_row + 2, pc.index)
    if _is_two_row(rows, header_row):
        data_start = header_row + 2
    layout = DetectedLayout(
        header_row=header_row,
        data_start_row=data_start,
        name_col=roles.get("name"),
        article_col=roles.get("article"),
        chars_col=roles.get("chars"),
        unit_col=roles.get("unit"),
        manufacturer_col=roles.get("manufacturer"),
        price_columns=price_columns,
    )
    nonempty = sum(1 for c in header if _norm(c))
    matched = len(roles) + len(price_columns)
    layout.confidence = round(matched / nonempty, 2) if nonempty else 0.0
    return layout
```

> Примечание: `_detect_price_columns` и `_is_two_row` добавляются в Task 3. Чтобы тесты Task 2 прошли (одностишные раскладки), временно добавить минимальные версии:

```python
def _is_two_row(rows: Rows, header_row: int) -> bool:
    return False


def _detect_price_columns(rows: Rows, header_row: int) -> list[PriceColumn]:
    out: list[PriceColumn] = []
    for col, cell in enumerate(rows[header_row]):
        norm = _norm(cell)
        if not norm or _match_role(norm):
            continue
        if _is_price_word(norm):
            out.append(PriceColumn(index=col, label=str(cell).strip(),
                                   on_request=_on_request_label(norm)))
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_detect.py -q`
Expected: PASS (4 теста; двухстрочные KONTROL/PRICETIN — в Task 3).

- [ ] **Step 6: Commit**

```bash
git add backend/tests/fixtures backend/app/catalog/detect.py backend/tests/test_detect.py
git commit -m "feat(catalog): detect_layout — авто-определение ролей колонок (одностишные шапки)"
```

---

## Task 3: detect_layout — двухстрочные шапки + у.е. + уверенность

**Files:**
- Modify: `backend/app/catalog/detect.py`
- Test: `backend/tests/test_detect.py`

- [ ] **Step 1: Write failing tests for two-row headers and у.е.**

Добавить в `backend/tests/test_detect.py`:

```python
def test_detect_kontrol_two_row():
    d = detect_layout(P.KONTROL)
    assert d.header_row == 1
    assert d.data_start_row == 3          # пропускаем строку подписей 1/2/3
    assert d.name_col == 2
    assert d.chars_col == 3
    assert d.manufacturer_col == 1
    assert d.article_col is None
    assert [p.index for p in d.price_columns] == [4, 5, 6]


def test_detect_pricetin_two_row_with_spacer():
    d = detect_layout(P.PRICETIN)
    assert d.header_row == 4
    assert d.data_start_row == 6
    assert d.name_col == 3
    assert d.article_col == 2              # "Код"
    assert d.chars_col == 4                # "Описание"
    assert d.manufacturer_col == 5
    assert d.unit_col == 6                 # "Вал./ Ед. изм."
    assert [p.index for p in d.price_columns] == [7, 8, 9]


def test_detect_akkum_on_request_columns():
    d = detect_layout(P.AKKUM)
    assert all(p.on_request for p in d.price_columns)
    assert [p.index for p in d.price_columns] == [3, 4, 5, 6, 7]


def test_detect_returns_none_when_no_header():
    assert detect_layout([["мусор", None], [None, None]]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_detect.py -q`
Expected: FAIL на новых (price_columns пустые / data_start_row неверный для KONTROL/PRICETIN).

- [ ] **Step 3: Replace _is_two_row and _detect_price_columns with full versions**

В `backend/app/catalog/detect.py` заменить временные `_is_two_row` и `_detect_price_columns` на:

```python
def _generic_price_col(header: list) -> int | None:
    for col, cell in enumerate(header):
        if _norm(cell) in GENERIC_PRICE:
            return col
    return None


def _is_two_row(rows: Rows, header_row: int) -> bool:
    header = rows[header_row]
    gen = _generic_price_col(header)
    if gen is None or header_row + 1 >= len(rows):
        return False
    sub = rows[header_row + 1]
    return any(c is not None and str(c).strip() for c in sub[gen:])


def _detect_price_columns(rows: Rows, header_row: int) -> list[PriceColumn]:
    header = rows[header_row]
    if _is_two_row(rows, header_row):
        gen = _generic_price_col(header)
        on_req = _on_request_label(_norm(header[gen]))
        sub = rows[header_row + 1]
        out: list[PriceColumn] = []
        for col in range(gen, len(sub)):
            val = sub[col]
            if val is not None and str(val).strip():
                out.append(PriceColumn(index=col, label=f"Цена {str(val).strip()}",
                                       on_request=on_req))
        return out
    out = []
    for col, cell in enumerate(header):
        norm = _norm(cell)
        if not norm or _match_role(norm):
            continue
        if _is_price_word(norm):
            out.append(PriceColumn(index=col, label=str(cell).strip(),
                                   on_request=_on_request_label(norm)))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_detect.py -q`
Expected: PASS (все 8 тестов).

- [ ] **Step 5: Lint**

Run: `./.venv/Scripts/ruff.exe check app/catalog/detect.py`
Expected: All checks passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/catalog/detect.py backend/tests/test_detect.py
git commit -m "feat(catalog): detect_layout — двухстрочные шапки, колонки у.е., уверенность"
```

---

## Task 4: Схемы — ColumnMapping, DetectedLayoutOut, ItemOut, ImportSheetMapping

**Files:**
- Modify: `backend/app/catalog/schemas.py`
- Test: `backend/tests/test_catalog_schemas.py` (создать)

- [ ] **Step 1: Write the failing test**

Создать `backend/tests/test_catalog_schemas.py`:

```python
from app.catalog.schemas import ColumnMapping, DetectedLayoutOut, ImportSheetMapping


def test_column_mapping_new_fields_optional():
    m = ColumnMapping(name_col=0)
    assert m.manufacturer_col is None
    assert m.header_row == 0
    assert m.data_start_row is None
    assert m.on_request_cols == []


def test_detected_layout_out_roundtrip():
    d = DetectedLayoutOut(
        header_row=1, data_start_row=3, name_col=2,
        price_columns=[{"index": 4, "label": "Цена 1", "sample": "100",
                        "on_request": False}],
    )
    assert d.price_columns[0].index == 4


def test_import_sheet_mapping():
    s = ImportSheetMapping(name="Лист1", mapping=ColumnMapping(name_col=0))
    assert s.name == "Лист1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_catalog_schemas.py -q`
Expected: FAIL — `ImportError` / `ValidationError` (поля не существуют).

- [ ] **Step 3: Update schemas.py**

В `backend/app/catalog/schemas.py` заменить класс `ColumnMapping` (строки 6-14) на:

```python
class ColumnMapping(BaseModel):
    """Маппинг колонок листа: индексы; price_cols: {price_level_id: column_index}.
    on_request_cols — индексы ценовых колонок «по запросу» (у.е.) → цена 0 + отметка."""

    name_col: int
    article_col: int | None = None
    unit_col: int | None = None
    category_col: int | None = None
    characteristics_col: int | None = None
    manufacturer_col: int | None = None
    header_row: int = 0
    data_start_row: int | None = None
    price_cols: dict[int, int] = Field(default_factory=dict)
    on_request_cols: list[int] = Field(default_factory=list)
```

Добавить после класса `ColumnMapping` (перед `PriceLevelIn`):

```python
class PriceColumnOut(BaseModel):
    index: int
    label: str
    sample: str = ""
    on_request: bool = False


class DetectedLayoutOut(BaseModel):
    header_row: int
    data_start_row: int
    name_col: int | None = None
    article_col: int | None = None
    chars_col: int | None = None
    unit_col: int | None = None
    manufacturer_col: int | None = None
    price_columns: list[PriceColumnOut] = Field(default_factory=list)
    confidence: float = 0.0


class ImportSheetMapping(BaseModel):
    name: str
    mapping: ColumnMapping
```

Добавить в `SheetOut` поле `detected` (после `columns`):

```python
class SheetOut(BaseModel):
    name: str
    row_count: int
    header_row: int
    columns: list[ColumnOut]
    detected: DetectedLayoutOut | None = None
```

Добавить в `ItemOut` после `kind: str` (строка 84):

```python
    manufacturer: str | None = None
    price_on_request: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_catalog_schemas.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog/schemas.py backend/tests/test_catalog_schemas.py
git commit -m "feat(catalog): схемы — ColumnMapping/DetectedLayout/ItemOut/ImportSheetMapping"
```

---

## Task 5: parse_rows — классификация строк, производитель, ед.изм, категория, у.е.

**Files:**
- Modify: `backend/app/catalog/importer.py:14-86`
- Test: `backend/tests/test_parse_rows.py` (создать)

- [ ] **Step 1: Write the failing tests**

Создать `backend/tests/test_parse_rows.py`:

```python
from decimal import Decimal

from app.catalog.importer import parse_rows
from app.catalog.schemas import ColumnMapping
from tests.fixtures import pricelists as P

# Уровни цен: id 10/11/12 → колонки берём из detected при импорте; здесь задаём вручную.


def test_bolid_products_with_two_prices():
    m = ColumnMapping(name_col=0, characteristics_col=1, article_col=3,
                      header_row=0, data_start_row=1, price_cols={10: 5, 11: 6})
    rows = parse_rows(P.BOLID, m)
    assert len(rows) == 2
    assert rows[0].name == "Сириус"
    assert rows[0].article == "1-520-887-052"
    assert rows[0].prices == {10: Decimal("36159.53"), 11: Decimal("33378.03")}
    assert rows[0].price_on_request is False


def test_kontrol_category_capture_and_zvonite():
    m = ColumnMapping(name_col=2, characteristics_col=3, manufacturer_col=1,
                      header_row=1, data_start_row=3, price_cols={10: 4, 11: 5, 12: 6})
    rows = parse_rows(P.KONTROL, m)
    # 2 товара (категории 1.1.1 пропущены, но запомнены)
    assert [r.name for r in rows] == ["CNC-02-IP", "NMI-08"]
    r = rows[0]
    assert r.manufacturer == "Parsec"
    assert r.category == "Интегрированная система"   # ближайшая категория сверху
    assert r.prices[10] == Decimal("24864")
    assert r.prices[12] == Decimal("0")              # "звоните" → 0
    assert r.price_on_request is True


def test_pricetin_unit_from_text_and_category():
    m = ColumnMapping(name_col=3, article_col=2, characteristics_col=4,
                      manufacturer_col=5, unit_col=6, header_row=4, data_start_row=6,
                      price_cols={10: 7, 11: 8, 12: 9})
    rows = parse_rows(P.PRICETIN, m)
    assert [r.name for r in rows] == ["DD-01", "CM-800"]
    assert rows[0].unit == "шт"                       # "руб./шт" → "шт"
    assert rows[0].category == "Извещатели охранные"
    assert rows[0].article == "319298"


def test_akkum_on_request_columns_zero_price():
    m = ColumnMapping(name_col=0, characteristics_col=2, article_col=10,
                      header_row=3, data_start_row=4,
                      price_cols={10: 3, 11: 4}, on_request_cols=[3, 4])
    rows = parse_rows(P.AKKUM, m)
    assert len(rows) == 1
    assert rows[0].prices == {10: Decimal("0"), 11: Decimal("0")}
    assert rows[0].price_on_request is True


def test_product_without_price_has_article_warns():
    data = [["Наименование", "Код", "Цена"],
            ["Болт", "К1", ""]]
    m = ColumnMapping(name_col=0, article_col=1, header_row=0, data_start_row=1,
                      price_cols={10: 2})
    rows = parse_rows(data, m)
    assert len(rows) == 1
    assert rows[0].problems == ["Нет ни одной цены"]


def test_blank_row_skipped_silently():
    data = [["Наименование", "Цена"], [None, None], ["Кабель", "100"]]
    m = ColumnMapping(name_col=0, header_row=0, data_start_row=1, price_cols={10: 1})
    rows = parse_rows(data, m)
    assert [r.name for r in rows] == ["Кабель"]
```

> У `parse_rows` ровно два позиционных аргумента: `(rows, mapping)` (+ опц. `default_category`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_parse_rows.py -q`
Expected: FAIL — `parse_rows` имеет старую сигнатуру `(rows, header_row, mapping, ...)`.

- [ ] **Step 3: Rewrite ParsedRow and parse_rows**

В `backend/app/catalog/importer.py` заменить `ParsedRow` (строки 14-23) и `parse_rows` (строки 48-86).

Новый `ParsedRow` (добавить два поля):

```python
@dataclass
class ParsedRow:
    name: str
    article: str = ""
    unit: str = "шт"
    category: str = ""
    characteristics: str = ""
    manufacturer: str = ""
    price_on_request: bool = False
    prices: dict[int, Decimal] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
```

Добавить вспомогательные функции и переписать `parse_rows` (вместо старой):

```python
ON_REQUEST_PHRASES = ("звоните", "по запросу", "уточняйте", "уточнить",
                      "договорная", "запрос", "прайс")


def _clean_unit(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "шт"
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1].strip()
    return raw or "шт"


def _is_on_request_text(raw: str) -> bool:
    low = raw.strip().lower()
    return any(p in low for p in ON_REQUEST_PHRASES)


def _category_text(row: list, mapping: ColumnMapping) -> str:
    """Текст строки-категории: имя, иначе производитель, иначе любая описательная."""
    for col in (mapping.name_col, mapping.manufacturer_col, mapping.characteristics_col):
        if col is not None:
            t = _cell(row, col)
            if t:
                return t
    for cell in row:
        if cell is not None and str(cell).strip() and not str(cell).strip().isdigit():
            return str(cell).strip()
    return ""


def parse_rows(rows: Rows, mapping: ColumnMapping, default_category: str = "") -> list[ParsedRow]:
    data_start = mapping.data_start_row if mapping.data_start_row is not None \
        else mapping.header_row + 1
    on_request_cols = set(mapping.on_request_cols)
    parsed: list[ParsedRow] = []
    current_category = ""
    for row in rows[data_start:]:
        name = _cell(row, mapping.name_col)
        prices: dict[int, Decimal] = {}
        on_request = False
        price_problems: list[str] = []
        for level_id, col in mapping.price_cols.items():
            raw = _cell(row, col)
            if not raw:
                continue
            if col in on_request_cols or _is_on_request_text(raw):
                prices[level_id] = Decimal("0.00")
                on_request = True
                continue
            try:
                value = _parse_price(raw)
            except InvalidOperation:
                price_problems.append(f"Цена не распознана: «{raw}» (колонка {col + 1})")
                continue
            if value < 0:
                price_problems.append(f"Отрицательная цена: {value} (колонка {col + 1})")
                continue
            prices[level_id] = value

        has_article = bool(_cell(row, mapping.article_col))
        if not prices and not price_problems:
            # нет цен: категория, товар-без-цены или разделитель
            if not name and not has_article:
                text = _category_text(row, mapping)
                if text:
                    current_category = text
                continue  # категория или пустой разделитель
            if not name:
                continue
            item = _build_row(row, mapping, name, current_category, default_category,
                              prices, on_request)
            item.problems.append("Нет ни одной цены")
            parsed.append(item)
            continue

        if not name:
            continue
        item = _build_row(row, mapping, name, current_category, default_category,
                          prices, on_request)
        item.problems.extend(price_problems)
        parsed.append(item)
    return parsed


def _build_row(row, mapping, name, current_category, default_category, prices,
               on_request) -> ParsedRow:
    category = (current_category or _cell(row, mapping.category_col) or default_category)
    return ParsedRow(
        name=name,
        article=_cell(row, mapping.article_col),
        unit=_clean_unit(_cell(row, mapping.unit_col)),
        category=category,
        characteristics=_cell(row, mapping.characteristics_col),
        manufacturer=_cell(row, mapping.manufacturer_col),
        price_on_request=on_request,
        prices=prices,
    )
```

> Удалить старые строки `parse_rows` (54-86), включая `header = rows[header_row]`, `header_name`, и старую логику `if name == header_name`. Повторы шапки посреди листа теперь невозможны: данные начинаются с `data_start`, а строки без цен/имени/артикула отсеиваются как категории/разделители.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_parse_rows.py -q`
Expected: PASS (6 тестов).

- [ ] **Step 5: Lint**

Run: `./.venv/Scripts/ruff.exe check app/catalog/importer.py`
Expected: All checks passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/catalog/importer.py backend/tests/test_parse_rows.py
git commit -m "feat(catalog): parse_rows — классификация строк, производитель, ед.изм, у.е."
```

---

## Task 6: import_parsed — запись manufacturer и price_on_request

**Files:**
- Modify: `backend/app/catalog/importer.py:117-184` (функция `import_parsed`)
- Test: `backend/tests/test_importer.py` (создать или дополнить)

- [ ] **Step 1: Write the failing test**

Создать `backend/tests/test_importer.py`:

```python
from decimal import Decimal

from app.catalog.importer import ParsedRow, import_parsed
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, Supplier


def _supplier_level(db):
    sup = Supplier(name="Опт-С"); db.add(sup); db.commit()
    lvl = PriceLevel(name="Розница"); db.add(lvl); db.commit()
    return sup, lvl


def test_import_writes_manufacturer_and_on_request(db_session):
    sup, lvl = _supplier_level(db_session)
    parsed = [
        ParsedRow(name="Камера", article="A1", manufacturer="Optimus",
                  price_on_request=True, prices={lvl.id: Decimal("0.00")}),
    ]
    import_parsed(db_session, sup.id, "p.xlsx", parsed, kind="material")
    item = db_session.scalars(
        __import__("sqlalchemy").select(CatalogItem)).one()
    assert item.manufacturer == "Optimus"
    assert item.price_on_request is True
    price = db_session.scalars(__import__("sqlalchemy").select(ItemPrice)).one()
    assert price.value == Decimal("0.00")


def test_import_updates_on_request_flag(db_session):
    sup, lvl = _supplier_level(db_session)
    import_parsed(db_session, sup.id, "p.xlsx",
                  [ParsedRow(name="К", article="A1", price_on_request=True,
                             prices={lvl.id: Decimal("0")})], kind="material")
    import_parsed(db_session, sup.id, "p2.xlsx",
                  [ParsedRow(name="К", article="A1", manufacturer="X",
                             price_on_request=False, prices={lvl.id: Decimal("99")})],
                  kind="material")
    item = db_session.scalars(__import__("sqlalchemy").select(CatalogItem)).one()
    assert item.price_on_request is False
    assert item.manufacturer == "X"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_importer.py -q`
Expected: FAIL — `import_parsed` не пишет `manufacturer`/`price_on_request`.

- [ ] **Step 3: Update import_parsed**

В `backend/app/catalog/importer.py`, в `import_parsed`:

В ветке создания позиции (`item = CatalogItem(...)`, строки ~151-159) добавить поля:

```python
            item = CatalogItem(
                supplier_id=supplier_id,
                name=row.name,
                article=row.article,
                unit=row.unit,
                category=row.category,
                kind=kind,
                manufacturer=row.manufacturer or None,
                price_on_request=row.price_on_request,
                characteristics_raw=row.characteristics or None,
            )
```

В ветке обновления (`else:`, строки ~163-169) добавить:

```python
        else:
            item.unit = row.unit
            item.category = row.category or item.category
            item.manufacturer = row.manufacturer or item.manufacturer
            item.price_on_request = row.price_on_request
            if row.characteristics and row.characteristics != item.characteristics_raw:
                item.characteristics_raw = row.characteristics
                item.characteristics = None
            summary.items_updated += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_importer.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog/importer.py backend/tests/test_importer.py
git commit -m "feat(catalog): import_parsed пишет manufacturer и price_on_request"
```

---

## Task 7: Роутер — inspect отдаёт detected, import принимает по-листовый маппинг

**Files:**
- Modify: `backend/app/catalog/router.py:131-197` (inspect, import), `:221-233` (ItemOut)
- Test: `backend/tests/test_catalog_import_api.py` (создать)

- [ ] **Step 1: Write the failing test**

Создать `backend/tests/test_catalog_import_api.py`:

```python
import io
import json

from openpyxl import Workbook

from app.auth.models import User
from app.catalog.models import CatalogItem, PriceLevel, Supplier
from app.core.security import create_access_token


def _admin(db):
    u = User(email="a@x.ru", name="A", role="admin", status="active")
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _xlsx(rows) -> bytes:
    wb = Workbook(); ws = wb.active
    for r in rows:
        ws.append(["" if c is None else c for c in r])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def test_inspect_returns_detected(client, db_session):
    a = _admin(db_session)
    rows = [["Наименование", "Код", "Цена"], ["Кабель", "K1", "100"]]
    files = {"file": ("p.xlsx", _xlsx(rows),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/api/catalog/inspect", files=files, headers=_hdr(a))
    assert r.status_code == 200, r.text
    sheet = r.json()["sheets"][0]
    assert sheet["detected"]["name_col"] == 0
    assert sheet["detected"]["price_columns"][0]["index"] == 2


def test_import_per_sheet_mapping(client, db_session):
    a = _admin(db_session)
    sup = Supplier(name="S"); db_session.add(sup)
    lvl = PriceLevel(name="Розница"); db_session.add(lvl); db_session.commit()
    rows = [["Наименование", "Код", "Цена"], ["Кабель", "K1", "100"]]
    files = {"file": ("p.xlsx", _xlsx(rows),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    mapping = {"name_col": 0, "article_col": 1, "header_row": 0, "data_start_row": 1,
               "price_cols": {str(lvl.id): 2}}
    data = {
        "supplier_id": str(sup.id), "kind": "material",
        "sheet_mappings": json.dumps([{"name": "Sheet", "mapping": mapping}]),
    }
    r = client.post("/api/catalog/import", files=files, data=data, headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json()["items_created"] == 1
    item = db_session.scalars(__import__("sqlalchemy").select(CatalogItem)).one()
    assert item.name == "Кабель"
```

> Примечание: имя листа по умолчанию у openpyxl — «Sheet».

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_catalog_import_api.py -q`
Expected: FAIL — `detected` отсутствует; `import` ждёт старые поля `sheets`/`mapping`.

- [ ] **Step 3: Update inspect endpoint**

В `backend/app/catalog/router.py` импортировать detect и схемы. В импортах модуля (строка 10) добавить `detect` к списку:

```python
from app.catalog import characteristics as ch_service
from app.catalog import detect, importer, parser, service
```

В импортах схем (строки 12-27) добавить `DetectedLayoutOut`, `ImportSheetMapping`, `PriceColumnOut`.

Заменить тело `inspect_file` (строки 132-144):

```python
async def inspect_file(file: UploadFile = File(...)):
    tables = _load_tables_or_415(await _read_limited(file), file.filename or "")
    sheets = []
    for name, rows in tables.items():
        header_row = parser.detect_header_row(rows)
        columns = [
            ColumnOut(index=c.index, header=c.header, samples=c.samples)
            for c in parser.extract_columns(rows, header_row)
        ]
        layout = detect.detect_layout(rows)
        detected = None
        if layout is not None:
            detected = DetectedLayoutOut(
                header_row=layout.header_row,
                data_start_row=layout.data_start_row,
                name_col=layout.name_col,
                article_col=layout.article_col,
                chars_col=layout.chars_col,
                unit_col=layout.unit_col,
                manufacturer_col=layout.manufacturer_col,
                price_columns=[
                    PriceColumnOut(index=p.index, label=p.label, sample=p.sample,
                                   on_request=p.on_request)
                    for p in layout.price_columns
                ],
                confidence=layout.confidence,
            )
        sheets.append(
            SheetOut(name=name, row_count=len(rows), header_row=header_row,
                     columns=columns, detected=detected)
        )
    return InspectOut(sheets=sheets)
```

- [ ] **Step 4: Update import endpoint**

Заменить сигнатуру и тело `import_file` (строки 150-197):

```python
async def import_file(
    file: UploadFile = File(...),
    supplier_id: int = Form(...),
    kind: str = Form(...),
    sheet_mappings: str = Form(...),
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
        items = [ImportSheetMapping.model_validate(x) for x in json_lib.loads(sheet_mappings)]
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Невалидный JSON в sheet_mappings")
    if not items:
        raise HTTPException(status_code=422, detail="Не выбран ни один лист")

    tables = _load_tables_or_415(await _read_limited(file), file.filename or "")
    parsed: list[importer.ParsedRow] = []
    for sm in items:
        if sm.name not in tables:
            raise HTTPException(status_code=422, detail=f"Лист «{sm.name}» не найден")
        parsed.extend(
            importer.parse_rows(
                tables[sm.name],
                sm.mapping,
                default_category=sm.name if use_sheet_as_category else "",
            )
        )

    try:
        summary = importer.import_parsed(
            db, supplier_id, file.filename or "import", parsed, kind=kind
        )
    except Exception:
        db.rollback()
        raise
    if save_mapping and items:
        supplier.column_mapping_template = items[0].mapping.model_dump()
        db.commit()
    return ImportSummaryOut(**summary.__dict__)
```

- [ ] **Step 5: Update ItemOut mapping in list_items**

В `list_items` (строки 221-233) добавить новые поля в `ItemOut(...)`:

```python
        ItemOut(
            id=i.id,
            supplier_id=i.supplier_id,
            name=i.name,
            article=i.article,
            unit=i.unit,
            category=i.category,
            kind=i.kind,
            manufacturer=i.manufacturer,
            price_on_request=i.price_on_request,
            prices=prices.get(i.id, {}),
            characteristics=i.characteristics,
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_catalog_import_api.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/catalog/router.py backend/tests/test_catalog_import_api.py
git commit -m "feat(catalog): inspect отдаёт detected, import принимает по-листовый маппинг"
```

---

## Task 8: Сквозные тесты импорта всех 6 форматов + полный прогон бэкенда

**Files:**
- Test: `backend/tests/test_import_formats.py` (создать)

- [ ] **Step 1: Write end-to-end format tests**

Создать `backend/tests/test_import_formats.py`:

```python
from decimal import Decimal

from sqlalchemy import select

from app.catalog import detect
from app.catalog.importer import import_parsed, parse_rows
from app.catalog.models import CatalogItem, PriceLevel, Supplier
from app.catalog.schemas import ColumnMapping
from tests.fixtures import pricelists as P


def _mapping_from_layout(layout, level_ids):
    """ColumnMapping из detected: ценовые колонки по порядку → переданные уровни."""
    price_cols = {level_ids[i]: pc.index for i, pc in enumerate(layout.price_columns)
                  if i < len(level_ids)}
    on_req = [pc.index for pc in layout.price_columns if pc.on_request]
    return ColumnMapping(
        name_col=layout.name_col, article_col=layout.article_col,
        unit_col=layout.unit_col, characteristics_col=layout.chars_col,
        manufacturer_col=layout.manufacturer_col, header_row=layout.header_row,
        data_start_row=layout.data_start_row, price_cols=price_cols,
        on_request_cols=on_req,
    )


def _setup(db, n_levels=3):
    sup = Supplier(name="S"); db.add(sup); db.commit()
    levels = [PriceLevel(name=f"L{i}", sort_order=i) for i in range(n_levels)]
    db.add_all(levels); db.commit()
    return sup, [l.id for l in levels]


def _run(db, rows, n_levels=3):
    sup, lids = _setup(db, n_levels)
    layout = detect.detect_layout(rows)
    assert layout is not None
    parsed = parse_rows(rows, _mapping_from_layout(layout, lids))
    import_parsed(db, sup.id, "p.xlsx", parsed, kind="material")
    return db.scalars(select(CatalogItem).order_by(CatalogItem.id)).all()


def test_e2e_bolid(db_session):
    items = _run(db_session, P.BOLID, n_levels=2)
    assert {i.name for i in items} == {"Сириус", "С2000-М"}
    assert all(not i.price_on_request for i in items)


def test_e2e_kontrol_categories_and_zvonite(db_session):
    items = _run(db_session, P.KONTROL)
    assert {i.name for i in items} == {"CNC-02-IP", "NMI-08"}
    assert all(i.category == "Интегрированная система" for i in items)
    assert all(i.price_on_request for i in items)        # звоните в 3-м уровне


def test_e2e_pricetin_unit_and_manufacturer(db_session):
    items = _run(db_session, P.PRICETIN)
    by_name = {i.name: i for i in items}
    assert by_name["DD-01"].unit == "шт"
    assert by_name["DD-01"].manufacturer == "CARDDEX"
    assert by_name["DD-01"].category == "Извещатели охранные"


def test_e2e_optimus_net_no_corruption(db_session):
    """Сдвинутый лист: характеристики НЕ содержат цену (главный баг старого импорта)."""
    items = _run(db_session, P.OPTIMUS_NET)
    item = items[0]
    assert item.name == "Коммутатор U1IC"
    assert item.characteristics_raw == "8 портов"   # не "3034" (цена)
    assert not item.price_on_request


def test_e2e_akkum_on_request(db_session):
    items = _run(db_session, P.AKKUM, n_levels=5)
    assert items[0].price_on_request is True
```

- [ ] **Step 2: Run format tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_import_formats.py -q`
Expected: PASS (5 тестов).

- [ ] **Step 3: Full backend suite + lint**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: все тесты зелёные (новые + существующие). Если `tests/test_import.py`/старые тесты использовали `parse_rows(rows, header_row, mapping, ...)` или import-поля `sheets`/`mapping` — обновить их под новую сигнатуру (см. Task 5/7).

Run: `./.venv/Scripts/ruff.exe check app/`
Expected: All checks passed.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_import_formats.py
git commit -m "test(catalog): сквозные тесты импорта 6 форматов + проверка от порчи"
```

---

## Task 9: Frontend — типы api/catalog.ts + по-листовый импорт

**Files:**
- Modify: `frontend/src/api/catalog.ts`
- Test: `frontend/src/api/catalog.test.ts` (создать)

- [ ] **Step 1: Write the failing test**

Создать `frontend/src/api/catalog.test.ts`:

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { importFile, type ImportParams } from "./catalog";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("access_token", "t");
});

describe("importFile", () => {
  it("отправляет sheet_mappings как JSON", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ price_list_id: 1, version: 1, items_created: 1,
        items_updated: 0, prices_written: 1, price_changes: 0, rows_skipped: 0,
        problems: [] }), { status: 200 }),
    );
    const params: ImportParams = {
      file: new File(["x"], "p.xlsx"),
      supplier_id: 1,
      kind: "material",
      sheet_mappings: [{ name: "Sheet", mapping: { name_col: 0, price_cols: {} } }],
      use_sheet_as_category: false,
      save_mapping: false,
    };
    await importFile(params);
    const body = spy.mock.calls[0][1]!.body as FormData;
    expect(body.get("sheet_mappings")).toContain("\"name\":\"Sheet\"");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (из `frontend`): `npm run test -- catalog.test`
Expected: FAIL — `ImportParams` имеет `sheets`/`mapping`, не `sheet_mappings`.

- [ ] **Step 3: Update types and importFile**

В `frontend/src/api/catalog.ts`:

Заменить тип `ColumnMapping` (строки 5-12):

```ts
export type ColumnMapping = {
  name_col: number;
  article_col: number | null;
  unit_col: number | null;
  category_col: number | null;
  characteristics_col: number | null;
  manufacturer_col?: number | null;
  header_row?: number;
  data_start_row?: number | null;
  price_cols: Record<number, number>; // price_level_id -> column index
  on_request_cols?: number[];
};
```

Добавить типы определения (после `ColumnMapping`):

```ts
export type PriceColumn = {
  index: number;
  label: string;
  sample: string;
  on_request: boolean;
};

export type DetectedLayout = {
  header_row: number;
  data_start_row: number;
  name_col: number | null;
  article_col: number | null;
  chars_col: number | null;
  unit_col: number | null;
  manufacturer_col: number | null;
  price_columns: PriceColumn[];
  confidence: number;
};
```

В типе `Sheet` (строка 17) добавить `detected`:

```ts
export type Sheet = { name: string; row_count: number; header_row: number; columns: Column[]; detected: DetectedLayout | null };
```

В типе `CatalogItem` (строки 31-41) добавить:

```ts
  manufacturer: string | null;
  price_on_request: boolean;
```

Заменить тип `ImportParams` и функцию `importFile` (строки 73-92):

```ts
export type ImportSheetMapping = { name: string; mapping: ColumnMapping };

export type ImportParams = {
  file: File;
  supplier_id: number;
  kind: "material" | "work";
  sheet_mappings: ImportSheetMapping[];
  use_sheet_as_category: boolean;
  save_mapping: boolean;
};
export const importFile = (p: ImportParams) => {
  const form = new FormData();
  form.append("file", p.file);
  form.append("supplier_id", String(p.supplier_id));
  form.append("kind", p.kind);
  form.append("sheet_mappings", JSON.stringify(p.sheet_mappings));
  form.append("use_sheet_as_category", String(p.use_sheet_as_category));
  form.append("save_mapping", String(p.save_mapping));
  return apiUpload<ImportSummary>("/catalog/import", form);
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- catalog.test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/catalog.ts frontend/src/api/catalog.test.ts
git commit -m "feat(catalog-ui): типы detected + по-листовый payload импорта"
```

---

## Task 10: Frontend — ColumnMapper: производитель + привязка ценовых колонок к уровням

**Files:**
- Modify: `frontend/src/components/ColumnMapper.tsx`
- Test: `frontend/src/components/ColumnMapper.test.tsx` (создать)

- [ ] **Step 1: Write the failing test**

Создать `frontend/src/components/ColumnMapper.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ColumnMapper from "./ColumnMapper";
import type { Column, ColumnMapping, PriceLevel } from "../api/catalog";

const columns: Column[] = [
  { index: 0, header: "Наименование", samples: ["Кабель"] },
  { index: 1, header: "Производитель", samples: ["ДКС"] },
  { index: 2, header: "РОЗН.", samples: ["100"] },
];
const levels: PriceLevel[] = [{ id: 10, name: "Розница", sort_order: 0 }];

function setup(mapping: ColumnMapping) {
  const onChange = vi.fn();
  render(<ColumnMapper columns={columns} levels={levels} mapping={mapping} onChange={onChange} />);
  return onChange;
}

const base: ColumnMapping = {
  name_col: 0, article_col: null, unit_col: null, category_col: null,
  characteristics_col: null, manufacturer_col: null, price_cols: {},
};

describe("ColumnMapper", () => {
  it("имеет поле Производитель", () => {
    setup(base);
    expect(screen.getByLabelText("Производитель")).toBeInTheDocument();
  });

  it("меняет manufacturer_col", async () => {
    const onChange = setup(base);
    await userEvent.selectOptions(screen.getByLabelText("Производитель"), "1");
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ manufacturer_col: 1 }));
  });

  it("привязывает ценовую колонку к уровню", async () => {
    const onChange = setup(base);
    await userEvent.selectOptions(screen.getByLabelText("Цена: Розница"), "2");
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ price_cols: { 10: 2 } }),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- ColumnMapper`
Expected: FAIL — нет поля «Производитель».

- [ ] **Step 3: Add manufacturer field to ColumnMapper**

В `frontend/src/components/ColumnMapper.tsx`:

Расширить тип поля в `setField` (строка 25):

```tsx
  function setField(field: "name_col" | "article_col" | "unit_col" | "category_col" | "characteristics_col" | "manufacturer_col", value: string) {
```

Добавить блок «Производитель» в grid ролей (после блока «Характеристики», перед закрытием `</div>` грида, строка 99):

```tsx
        <label className="block">
          <span className="mb-1 block text-stone-600">Производитель</span>
          <select
            aria-label="Производитель"
            value={mapping.manufacturer_col ?? ""}
            onChange={(e) => setField("manufacturer_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- ColumnMapper`
Expected: PASS (3 теста — поле «Цена: Розница» уже есть в текущем компоненте).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ColumnMapper.tsx frontend/src/components/ColumnMapper.test.tsx
git commit -m "feat(catalog-ui): ColumnMapper — поле Производитель"
```

---

## Task 11: Frontend — ImportPage: предзаполнение из detected по каждому листу

**Files:**
- Modify: `frontend/src/pages/ImportPage.tsx`
- Test: `frontend/src/pages/ImportPage.test.tsx` (создать)

- [ ] **Step 1: Write the failing test**

Создать `frontend/src/pages/ImportPage.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { mappingFromDetected } from "./ImportPage";
import type { DetectedLayout, PriceLevel } from "../api/catalog";

const levels: PriceLevel[] = [
  { id: 10, name: "Розница", sort_order: 0 },
  { id: 11, name: "Опт", sort_order: 1 },
];

describe("mappingFromDetected", () => {
  it("строит ColumnMapping и привязывает цены по порядку к уровням", () => {
    const d: DetectedLayout = {
      header_row: 0, data_start_row: 1, name_col: 0, article_col: 1, chars_col: 2,
      unit_col: null, manufacturer_col: null,
      price_columns: [
        { index: 4, label: "Розн", sample: "100", on_request: false },
        { index: 5, label: "Опт", sample: "90", on_request: true },
      ],
      confidence: 0.9,
    };
    const m = mappingFromDetected(d, levels);
    expect(m.name_col).toBe(0);
    expect(m.article_col).toBe(1);
    expect(m.characteristics_col).toBe(2);
    expect(m.header_row).toBe(0);
    expect(m.data_start_row).toBe(1);
    expect(m.price_cols).toEqual({ 10: 4, 11: 5 });
    expect(m.on_request_cols).toEqual([5]);
  });

  it("дефолт name_col=0 если не определён", () => {
    const d: DetectedLayout = {
      header_row: 0, data_start_row: 1, name_col: null, article_col: null,
      chars_col: null, unit_col: null, manufacturer_col: null,
      price_columns: [], confidence: 0,
    };
    expect(mappingFromDetected(d, levels).name_col).toBe(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- ImportPage`
Expected: FAIL — `mappingFromDetected` не экспортирован.

- [ ] **Step 3: Add mappingFromDetected helper and per-sheet state**

В `frontend/src/pages/ImportPage.tsx`:

Добавить экспортируемый хелпер (после импортов, перед `type Step`):

```tsx
import type { ColumnMapping, DetectedLayout, ImportSheetMapping } from "../api/catalog";

export function mappingFromDetected(d: DetectedLayout, levels: PriceLevel[]): ColumnMapping {
  const price_cols: Record<number, number> = {};
  d.price_columns.forEach((pc, i) => {
    if (i < levels.length) price_cols[levels[i].id] = pc.index;
  });
  return {
    name_col: d.name_col ?? 0,
    article_col: d.article_col,
    unit_col: d.unit_col,
    category_col: null,
    characteristics_col: d.chars_col,
    manufacturer_col: d.manufacturer_col,
    header_row: d.header_row,
    data_start_row: d.data_start_row,
    price_cols,
    on_request_cols: d.price_columns.filter((p) => p.on_request).map((p) => p.index),
  };
}
```

> Удалить дублирующий импорт `type ColumnMapping` из общего блока импорта `../api/catalog` (строка 10), если он там есть, чтобы не было повторного объявления.

Заменить состояние одного `mapping` на словарь по листам. Заменить строку `const [mapping, setMapping] = useState<ColumnMapping>(EMPTY_MAPPING);` (строка 37) на:

```tsx
  const [mappings, setMappings] = useState<Record<string, ColumnMapping>>({});
```

В `doInspect` (строки 76-97) после получения `res` построить маппинги из detected по каждому листу:

```tsx
      const res = await inspectFile(file);
      setInspectResult(res);
      const allSheets = res.sheets.map((s) => s.name);
      setSelectedSheets(allSheets);
      const tmpl = suppliers.find((s) => s.id === supplierId)?.column_mapping_template as
        | ColumnMapping | undefined;
      const next: Record<string, ColumnMapping> = {};
      for (const s of res.sheets) {
        next[s.name] = s.detected
          ? mappingFromDetected(s.detected, levels)
          : (tmpl ?? EMPTY_MAPPING);
      }
      setMappings(next);
      setStep("map");
```

Изменить `mapColumns` (строки 55-58) и `ColumnMapper` так, чтобы редактировать маппинг текущего листа. Заменить вычисление колонок и рендер `ColumnMapper` (строка 257). Текущий лист для редактирования — первый выбранный:

```tsx
  const activeSheet = selectedSheets[0] ?? "";
  const mapColumns = useMemo(() => {
    const sheet = inspectResult?.sheets.find((s) => s.name === activeSheet);
    return sheet?.columns ?? [];
  }, [inspectResult, activeSheet]);
  const activeMapping = mappings[activeSheet] ?? EMPTY_MAPPING;
```

Заменить рендер `<ColumnMapper .../>` (строка 257):

```tsx
            <ColumnMapper
              columns={mapColumns}
              levels={levels}
              mapping={activeMapping}
              onChange={(m) => setMappings((cur) => ({ ...cur, [activeSheet]: m }))}
            />
```

Обновить `EMPTY_MAPPING` (строки 21-24) — добавить новые поля:

```tsx
const EMPTY_MAPPING: ColumnMapping = {
  name_col: 0, article_col: null, unit_col: null, category_col: null,
  characteristics_col: null, manufacturer_col: null, header_row: 0,
  data_start_row: null, price_cols: {}, on_request_cols: [],
};
```

Заменить вызов `importFile` в `doImport` (строки 113-121):

```tsx
      const sheet_mappings: ImportSheetMapping[] = selectedSheets.map((name) => ({
        name,
        mapping: mappings[name] ?? EMPTY_MAPPING,
      }));
      const res = await importFile({
        file,
        supplier_id: supplierId,
        kind,
        sheet_mappings,
        use_sheet_as_category: useSheetAsCategory,
        save_mapping: saveMapping,
      });
```

Обновить `reset` (строки 155-164): заменить `setMapping(EMPTY_MAPPING)` на `setMappings({})`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- ImportPage`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ImportPage.tsx frontend/src/pages/ImportPage.test.tsx
git commit -m "feat(catalog-ui): ImportPage — по-листовое предзаполнение из detected"
```

---

## Task 12: Frontend — CatalogPage: производитель + бейдж «уточнить стоимость»

**Files:**
- Modify: `frontend/src/pages/CatalogPage.tsx`
- Test: `frontend/src/pages/CatalogPage.test.tsx` (дополнить или создать)

**Опорные строки текущего файла:** ячейка цены — `CatalogPage.tsx:216` (`{it.prices[String(l.id)] ?? "—"}`), ячейка названия — `:204` (`<td className="text-stone-900">{it.name}</td>`). `it.prices` — `Record<string, string>` (ключи строковые).

- [ ] **Step 1: Write the failing test**

Создать `frontend/src/pages/CatalogPage.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { priceCellText } from "./CatalogPage";

describe("priceCellText", () => {
  it("показывает «уточнить» для price_on_request", () => {
    expect(priceCellText("0.00", true)).toBe("уточнить");
  });
  it("показывает цену, когда не on_request", () => {
    expect(priceCellText("100.00", false)).toBe("100.00");
  });
  it("прочерк, когда цены нет", () => {
    expect(priceCellText(undefined, false)).toBe("—");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- CatalogPage`
Expected: FAIL — `priceCellText` не экспортирован.

- [ ] **Step 3: Add helper and use it in rendering**

В `frontend/src/pages/CatalogPage.tsx` добавить экспортируемый хелпер перед `export default function CatalogPage()` (после `const PAGE_SIZE = 50;`, строка 15):

```tsx
export function priceCellText(value: string | undefined, onRequest: boolean): string {
  if (onRequest) return "уточнить";
  return value ?? "—";
}
```

Заменить ячейку цены (строки 214-218) на:

```tsx
                {levels.map((l) => (
                  <td key={l.id} className="text-right tabular-nums">
                    {priceCellText(it.prices[String(l.id)], it.price_on_request)}
                  </td>
                ))}
```

Заменить ячейку названия (строка 204) на:

```tsx
                <td className="text-stone-900">
                  {it.name}
                  {it.manufacturer && <span className="text-stone-400"> · {it.manufacturer}</span>}
                </td>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- CatalogPage`
Expected: PASS.

- [ ] **Step 5: Full frontend suite + build + lint**

Run: `npm run test`
Expected: все тесты зелёные.
Run: `npm run build` — успешно.
Run: `npm run lint` — 0 ошибок.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/CatalogPage.tsx frontend/src/pages/CatalogPage.test.tsx
git commit -m "feat(catalog-ui): показ производителя и бейджа «уточнить стоимость»"
```

---

## Финальная проверка (после всех задач)

- [ ] Бэкенд: `./.venv/Scripts/python.exe -m pytest -q` — всё зелёное; `./.venv/Scripts/ruff.exe check app/` — чисто.
- [ ] Фронтенд: `npm run test` / `npm run build` / `npm run lint` — всё зелёное.
- [ ] Холистическое ревью свежим субагентом.
- [ ] FF-merge в main, redeploy прода, миграция `d1e2f3a4b5c6` на боевом Postgres, health 200 (smetaapp + v-s-b.ru).
- [ ] Обновить память `project_smetaapp.md`.
