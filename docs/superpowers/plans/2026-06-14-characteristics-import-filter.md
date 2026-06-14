# Характеристики: импорт-колонка + фильтр Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox steps.

**Goal:** Колонка характеристик при импорте → сырьё в каталог; AI раскидывает в признаки (свободные ключи, единая терминология); фильтр каталога по признакам.

**Architecture:** `CatalogItem.characteristics_raw` (сырьё из колонки прайса) → `catalog_extract` структурирует в `characteristics` JSON → фасет-эндпоинт + фильтр в `search_items` → UI-фильтры на CatalogPage.

**Tech:** FastAPI+SQLAlchemy+Alembic; React+TS+Vite; pytest+Vitest. Head миграций: `b8c9d0e1f2a3`. Ветка `feat-characteristics-filter` (создана, спек закоммичен). Backend cmds: `./.venv/Scripts/python.exe -m pytest -q`, `./.venv/Scripts/ruff.exe check app/`. Frontend: `npm run test|build|lint`.

---

### Task 1: characteristics_raw + импорт-колонка

**Files:** Modify `backend/app/catalog/models.py`, `schemas.py` (ColumnMapping), `importer.py`; Create migration `c9d0e1f2a3b4_characteristics_raw.py`; Test `backend/tests/test_characteristics_import.py`

- [ ] **Step 1: Тест** `backend/tests/test_characteristics_import.py`

```python
from app.catalog import importer
from app.catalog.models import CatalogItem, Supplier
from app.catalog.schemas import ColumnMapping


def _rows():
    return [
        ["Наименование", "Артикул", "Характеристики"],
        ["Камера X", "A1", "2 Мп, объектив 2.8мм, IP67"],
    ]


def test_parse_rows_reads_characteristics_col():
    m = ColumnMapping(name_col=0, article_col=1, characteristics_col=2)
    parsed = importer.parse_rows(_rows(), 0, m)
    assert parsed[0].characteristics == "2 Мп, объектив 2.8мм, IP67"


def test_import_stores_raw_and_resets_on_change(db_session):
    sup = Supplier(name="S"); db_session.add(sup); db_session.commit()
    m = ColumnMapping(name_col=0, article_col=1, characteristics_col=2)
    parsed = importer.parse_rows(_rows(), 0, m)
    importer.import_parsed(db_session, sup.id, "f.xlsx", parsed, kind="material")
    it = db_session.scalars(__import__("sqlalchemy").select(CatalogItem)).first()
    assert it.characteristics_raw == "2 Мп, объектив 2.8мм, IP67"
    # имитируем уже извлечённые признаки
    it.characteristics = {"Разрешение": "2 Мп"}; db_session.commit()
    # повторный импорт с ИЗМЕНЁННЫМ сырьём → characteristics сбрасывается в None
    rows2 = [["Наименование", "Артикул", "Характеристики"], ["Камера X", "A1", "4 Мп, IP66"]]
    importer.import_parsed(db_session, sup.id, "f2.xlsx", importer.parse_rows(rows2, 0, m), kind="material")
    db_session.refresh(it)
    assert it.characteristics_raw == "4 Мп, IP66"
    assert it.characteristics is None
```

- [ ] **Step 2: Запустить — упадёт** — `pytest tests/test_characteristics_import.py -q`.

- [ ] **Step 3: Модель** — `backend/app/catalog/models.py`, в `CatalogItem` после `characteristics` добавить:

```python
    characteristics_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
```
Добавить `Text` в импорт `from sqlalchemy import (...)` если отсутствует (проверить шапку models.py — там уже JSON/JSONB; добавить `Text`).

- [ ] **Step 4: Миграция** `backend/alembic/versions/c9d0e1f2a3b4_characteristics_raw.py`

```python
"""catalog characteristics_raw

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-14 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c9d0e1f2a3b4'
down_revision: str | Sequence[str] | None = 'b8c9d0e1f2a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('catalog_items', sa.Column('characteristics_raw', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('catalog_items', 'characteristics_raw')
```

- [ ] **Step 5: ColumnMapping** — `backend/app/catalog/schemas.py`, в `ColumnMapping` после `category_col` добавить:

```python
    characteristics_col: int | None = None
```

- [ ] **Step 6: ParsedRow + parse_rows + import_parsed** — `backend/app/catalog/importer.py`:
  - в `class ParsedRow` после `category: str = ""` добавить `characteristics: str = ""`.
  - в `parse_rows`, в создании `ParsedRow(...)` добавить аргумент `characteristics=_cell(row, mapping.characteristics_col),`.
  - в `import_parsed`, ветка создания (`item = CatalogItem(...)`) добавить аргумент `characteristics_raw=row.characteristics or None,`; ветка обновления (`else:` после `summary.items_updated += 1` блока) — заменить на:

```python
        else:
            item.unit = row.unit
            item.category = row.category or item.category
            if row.characteristics and row.characteristics != item.characteristics_raw:
                item.characteristics_raw = row.characteristics
                item.characteristics = None  # сырьё изменилось → переизвлечь признаки
            summary.items_updated += 1
```

- [ ] **Step 7: Запустить — пройдёт** — `pytest tests/test_characteristics_import.py -q`.

- [ ] **Step 8: Commit** — `git add backend/app/catalog/models.py backend/app/catalog/schemas.py backend/app/catalog/importer.py backend/alembic/versions/c9d0e1f2a3b4_characteristics_raw.py backend/tests/test_characteristics_import.py && git commit -m "feat(catalog): characteristics_raw column + import mapping"`

---

### Task 2: extract_batch берёт сырьё + единая терминология

**Files:** Modify `backend/app/catalog/characteristics.py`; Test: дополнить `backend/tests/test_catalog_characteristics.py`

- [ ] **Step 1: Тест** — добавить в `backend/tests/test_catalog_characteristics.py`:

```python
def test_extract_uses_raw_as_source(db_session, monkeypatch):
    it = _item(db_session, name="Камера X")
    it.characteristics_raw = "2 Мп, объектив 2.8мм, IP67"
    db_session.commit()
    captured = {}
    def fake(db, purpose, messages, **k):
        captured["prompt"] = messages[-1]["content"]
        return {"items": [{"id": it.id, "characteristics": {"Разрешение": "2 Мп"}}]}
    monkeypatch.setattr(ai_service, "call_llm", fake)
    ch.extract_batch(db_session, batch=40)
    assert "2.8мм" in captured["prompt"]  # сырьё попало в промпт
    db_session.refresh(it)
    assert it.characteristics == {"Разрешение": "2 Мп"}
```

- [ ] **Step 2: Запустить — упадёт** — `pytest tests/test_catalog_characteristics.py::test_extract_uses_raw_as_source -q`.

- [ ] **Step 3: Реализовать** — в `backend/app/catalog/characteristics.py`, в `extract_batch`, заменить формирование `payload` и `prompt`:

```python
    payload = [
        {"id": it.id, "text": (it.characteristics_raw or it.name), "unit": it.unit, "kind": it.kind}
        for it in items
    ]
    prompt = (
        "Ты — инженер по оборудованию. Для каждой позиции извлеки технические "
        "характеристики из описания (text) в пары ключ-значение на русском. "
        "Используй ЕДИНУЮ терминологию ключей (Разрешение, Объектив, Фокусное расстояние, "
        "Температурный режим, Степень защиты, Питание, Матрица и т.п.) — одинаковые понятия "
        "обозначай одинаковым ключом. Значения кратко. Если данных нет — пустой объект {}. "
        "Верни строго JSON {\"items\":[{\"id\":<id>,\"characteristics\":{...}}]} по ВСЕМ позициям.\n\n"
        "ПОЗИЦИИ:\n"
        + "\n".join(f"  id={p['id']} | {p['text']} | {p['unit']} | {p['kind']}" for p in payload)
    )
```
(остальное в функции без изменений.)

- [ ] **Step 4: Запустить — пройдёт** — `pytest tests/test_catalog_characteristics.py -q`.

- [ ] **Step 5: Commit** — `git add backend/app/catalog/characteristics.py backend/tests/test_catalog_characteristics.py && git commit -m "feat(catalog): extract characteristics from raw with unified keys"`

---

### Task 3: фасеты + фильтр в search_items + items endpoint

**Files:** Modify `backend/app/catalog/service.py` (search_items facets), `router.py` (facets endpoint + items f-param); Test `backend/tests/test_catalog_facets.py`

- [ ] **Step 1: Тест** `backend/tests/test_catalog_facets.py`

```python
from app.auth.models import User
from app.catalog.models import CatalogItem, Supplier
from app.catalog.service import search_items
from app.core.security import create_access_token


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _items(db):
    sup = Supplier(name="S"); db.add(sup); db.commit()
    db.add_all([
        CatalogItem(supplier_id=sup.id, name="Камера A", article="1", unit="шт", kind="material",
                    characteristics={"Разрешение": "2 Мп", "Питание": "PoE"}),
        CatalogItem(supplier_id=sup.id, name="Камера B", article="2", unit="шт", kind="material",
                    characteristics={"Разрешение": "4 Мп", "Питание": "PoE"}),
    ])
    db.commit(); return sup


def test_search_items_facet_filter(db_session):
    _items(db_session)
    items, total = search_items(db_session, facets={"Разрешение": "2 Мп"})
    assert total == 1 and items[0].name == "Камера A"


def test_facets_endpoint_aggregates(client, db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    _items(db_session)
    body = client.get("/api/catalog/facets", headers=_hdr(u)).json()
    assert sorted(body["Разрешение"]) == ["2 Мп", "4 Мп"]
    assert body["Питание"] == ["PoE"]


def test_items_endpoint_facet_param(client, db_session):
    u = User(email="u2@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    _items(db_session)
    body = client.get("/api/catalog/items?f=Разрешение=4 Мп", headers=_hdr(u)).json()
    assert body["total"] == 1 and body["items"][0]["name"] == "Камера B"
```

- [ ] **Step 2: Запустить — упадёт** — `pytest tests/test_catalog_facets.py -q`.

- [ ] **Step 3: search_items facets** — `backend/app/catalog/service.py`, сигнатуру `search_items` дополнить параметром `facets: dict[str, str] | None = None` (после `offset`). После блоков token-фильтра и до `supplier_id` (или рядом) добавить:

```python
    for key, value in (facets or {}).items():
        query = query.where(CatalogItem.characteristics[key].as_string() == value)
```
Если SQLite-тест `test_search_items_facet_filter` упадёт на `.as_string()` — заменить на:
`from sqlalchemy import cast, String` и `query.where(cast(CatalogItem.characteristics[key], String) == value)`.

- [ ] **Step 4: эндпоинты** — `backend/app/catalog/router.py`:
  - импорт `from fastapi import ..., Query` (добавить Query к существующему импорту fastapi).
  - в `list_items` добавить параметр `f: list[str] = Query(default=[])` и распарсить:

```python
    facets = {}
    for pair in f:
        if "=" in pair:
            k, v = pair.split("=", 1)
            facets[k] = v
    items, total = service.search_items(db, q, supplier_id, kind, min(limit, 200), offset, facets=facets)
```
  (заменить существующий вызов `service.search_items(...)` на этот с `facets=facets`.)
  - добавить facets-эндпоинт:

```python
@router.get("/catalog/facets", dependencies=[Depends(require_active)])
def catalog_facets(
    supplier_id: int | None = None, kind: str | None = None, db: Session = Depends(get_db),
):
    query = select(CatalogItem.characteristics).where(CatalogItem.characteristics.isnot(None))
    if supplier_id is not None:
        query = query.where(CatalogItem.supplier_id == supplier_id)
    if kind is not None:
        query = query.where(CatalogItem.kind == kind)
    facets: dict[str, set] = {}
    for (chars,) in db.execute(query.limit(2000)).all():
        if not isinstance(chars, dict):
            continue
        for k, v in chars.items():
            if v:
                facets.setdefault(str(k), set()).add(str(v))
    return {k: sorted(vs)[:50] for k, vs in list(facets.items())[:40]}
```

- [ ] **Step 5: Запустить — пройдёт** — `pytest tests/test_catalog_facets.py -q`. Затем полный backend `pytest -q` + `ruff check app/`.

- [ ] **Step 6: Commit** — `git add backend/app/catalog/service.py backend/app/catalog/router.py backend/tests/test_catalog_facets.py && git commit -m "feat(catalog): facets endpoint + characteristics filter in search"`

---

### Task 4: frontend api (ColumnMapping + facets + listItems)

**Files:** Modify `frontend/src/api/catalog.ts`

- [ ] **Step 1: Изменения** в `frontend/src/api/catalog.ts`:
  - в тип `ColumnMapping` добавить `characteristics_col: number | null;` (если тип определён с полями name_col и т.д.).
  - изменить `listItems` чтобы принимать `facets?: Record<string, string>` и добавлять повторяемые `f=K=V`. Найти текущую `listItems` и заменить построение query: добавить для каждого `[k,v]` из facets `params.append("f", `${k}=${v}`)`.
  - добавить `getFacets`:

```ts
export const getFacets = (supplierId?: number, kind?: string) => {
  const p = new URLSearchParams();
  if (supplierId != null) p.set("supplier_id", String(supplierId));
  if (kind) p.set("kind", kind);
  const qs = p.toString();
  return api<Record<string, string[]>>(`/catalog/facets${qs ? `?${qs}` : ""}`);
};
```
  (Прочитать текущую реализацию `listItems`/`ColumnMapping` в файле и внести правки аккуратно; если `listItems` строит URL вручную — добавить facets-параметры к тому же URLSearchParams.)

- [ ] **Step 2: build** — `npm run build`. PASS (поправить типы при необходимости; в EMPTY_MAPPING в ImportPage добавить `characteristics_col: null`).

- [ ] **Step 3: Commit** — `git add frontend/src/api/catalog.ts frontend/src/pages/ImportPage.tsx && git commit -m "feat(catalog): api for facets + characteristics_col mapping"`

---

### Task 5: ColumnMapper — селектор «Характеристики»

**Files:** Modify `frontend/src/components/ColumnMapper.tsx`

- [ ] **Step 1: Изменения** — в `setField` тип-union расширить: `field: "name_col" | "article_col" | "unit_col" | "category_col" | "characteristics_col"`. После блока «Категория» (label) добавить аналогичный селектор:

```tsx
        <label className="block">
          <span className="mb-1 block text-stone-600">Характеристики</span>
          <select
            aria-label="Характеристики"
            value={mapping.characteristics_col ?? ""}
            onChange={(e) => setField("characteristics_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
```

- [ ] **Step 2: build/lint** — `npm run build` + `npm run lint`. PASS.

- [ ] **Step 3: Commit** — `git add frontend/src/components/ColumnMapper.tsx && git commit -m "feat(catalog): characteristics column selector in import mapper"`

---

### Task 6: CatalogPage — фасет-фильтры

**Files:** Modify `frontend/src/pages/CatalogPage.tsx`

- [ ] **Step 1: Изменения** — в `frontend/src/pages/CatalogPage.tsx`:
  - импорт: добавить `getFacets` к импорту из `../api/catalog`.
  - состояние: `const [facets, setFacets] = useState<Record<string, string[]>>({}); const [selected, setSelected] = useState<Record<string, string>>({});`.
  - effect: при изменении `supplierId`/`kind` подгружать фасеты и сбрасывать выбор:

```tsx
  useEffect(() => {
    setSelected({});
    void getFacets(supplierId === "" ? undefined : supplierId, kind || undefined)
      .then(setFacets).catch(() => setFacets({}));
  }, [supplierId, kind]);
```
  - в debounce-effect, вызывающем `listItems`, добавить `facets: Object.keys(selected).length ? selected : undefined,` и `selected` в массив зависимостей.
  - UI: после блока фильтров (поиск/поставщик/вид) добавить ряд фасет-выпадашек:

```tsx
        {Object.keys(facets).length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
            {Object.entries(facets).map(([key, values]) => (
              <select key={key} aria-label={`Фильтр: ${key}`} value={selected[key] ?? ""}
                onChange={(e) => {
                  setOffset(0);
                  setSelected((s) => {
                    const next = { ...s };
                    if (e.target.value === "") delete next[key]; else next[key] = e.target.value;
                    return next;
                  });
                }}
                className="rounded border border-stone-300 px-2 py-1">
                <option value="">{key}: любое</option>
                {values.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            ))}
            {Object.keys(selected).length > 0 && (
              <button onClick={() => { setOffset(0); setSelected({}); }} className="text-stone-500">Сбросить фильтры</button>
            )}
          </div>
        )}
```

- [ ] **Step 2: Проверка** — `npm run test` (все зелёные; CatalogPage без отдельного теста, проверяем сборкой), `npm run build`, `npm run lint`.

- [ ] **Step 3: Commit** — `git add frontend/src/pages/CatalogPage.tsx && git commit -m "feat(catalog): facet filters on catalog page"`

---

## Самопроверка плана

**Покрытие спека:** characteristics_raw+импорт-колонка (Task 1); extract из сырья+единые ключи (Task 2); фасеты+фильтр+items-param (Task 3); api (Task 4); ColumnMapper селектор (Task 5); CatalogPage фильтры (Task 6).

**Плейсхолдеры:** нет (Task 4/6 ссылаются на чтение существующего файла для аккуратной правки — структура известна).

**Согласованность:** `characteristics_raw` (модель Task1=миграция Task1); `ColumnMapping.characteristics_col` (схема Task1 = api Task4 = ColumnMapper Task5 = parse_rows Task1); `search_items(facets=)` (Task3) = items `f`-param (Task3) = `listItems facets` (Task4) = CatalogPage `selected` (Task6); `getFacets` (Task4)=facets endpoint (Task3)=CatalogPage (Task6). Миграция down_revision `b8c9d0e1f2a3` (текущий head). ⚠ Кросс-БД JSON-фильтр: `characteristics[key].as_string()` обязан пройти SQLite-тест `test_search_items_facet_filter`, иначе fallback на `cast(..., String)`.
