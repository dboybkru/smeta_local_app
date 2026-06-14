# Каталог — AI-характеристики оборудования Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI извлекает характеристики оборудования из названия позиции (пары ключ-значение), хранит в каталоге, авто при импорте; ассистент и каталог их используют.

**Architecture:** `CatalogItem.characteristics` JSON (nullable). Новая AI-цель `catalog_extract`. Batch-сервис `extract_batch` (`call_llm` по пачке позиций без хар-к) + эндпоинт `POST /api/catalog/extract-characteristics`. Фронт авто-циклит эндпоинт после импорта и по кнопке в каталоге; характеристики идут в кандидаты ассистента.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2 + Alembic; React 19 + TS + Vite; pytest + Vitest.

Backend: `D:\git\smeta_local_app\backend` (`.venv\Scripts\python.exe -m pytest`, `.venv\Scripts\ruff.exe check app/`). Frontend: `D:\git\smeta_local_app\frontend` (`npm run test|build|lint`). Ветка `phase6-catalog-characteristics` (создана, спек закоммичен).

---

### Task 1: модель + миграция + ItemOut

**Files:**
- Modify: `backend/app/catalog/models.py` (CatalogItem.characteristics)
- Create: `backend/alembic/versions/f6a7b8c9d0e1_catalog_characteristics.py`
- Modify: `backend/app/catalog/schemas.py` (ItemOut.characteristics)
- Modify: `backend/app/catalog/router.py` (list_items прокидывает characteristics)
- Test: `backend/tests/test_catalog_characteristics.py`

- [ ] **Step 1: Написать падающий тест** `backend/tests/test_catalog_characteristics.py`

```python
from app.auth.models import User
from app.catalog.models import CatalogItem, Supplier
from app.core.security import create_access_token


def _admin(db):
    u = User(email="a@x.ru", name="A", role="admin", status="active")
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _item(db, name="Камера IP 2Мп PoE"):
    sup = Supplier(name="P"); db.add(sup); db.commit()
    it = CatalogItem(supplier_id=sup.id, name=name, article="A", unit="шт", kind="material")
    db.add(it); db.commit(); db.refresh(it)
    return it


def test_item_characteristics_default_none_and_settable(db_session):
    it = _item(db_session)
    assert it.characteristics is None
    it.characteristics = {"Разрешение": "2 Мп", "Питание": "PoE"}
    db_session.commit(); db_session.refresh(it)
    assert it.characteristics["Питание"] == "PoE"


def test_list_items_returns_characteristics(client, db_session):
    a = _admin(db_session)
    it = _item(db_session)
    it.characteristics = {"Разрешение": "2 Мп"}
    db_session.commit()
    r = client.get("/api/catalog/items", headers=_hdr(a))
    assert r.status_code == 200, r.text
    item = next(x for x in r.json()["items"] if x["id"] == it.id)
    assert item["characteristics"] == {"Разрешение": "2 Мп"}
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_catalog_characteristics.py -q`. Expected: FAIL.

- [ ] **Step 3: Модель** — в `backend/app/catalog/models.py`, в класс `CatalogItem` добавить поле (после `kind`):

```python
    characteristics: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
```
(`JSON` и `JSONB` уже импортированы в этом файле.)

- [ ] **Step 4: Миграция** — создать `backend/alembic/versions/f6a7b8c9d0e1_catalog_characteristics.py`:

```python
"""catalog item characteristics + catalog_extract purpose

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-14 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: str | Sequence[str] | None = 'e5f6a7b8c9d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('catalog_items', sa.Column('characteristics', sa.JSON(), nullable=True))
    purposes = sa.table(
        'ai_purposes',
        sa.column('key', sa.String), sa.column('title', sa.String),
        sa.column('description', sa.Text), sa.column('enabled', sa.Boolean),
    )
    op.bulk_insert(purposes, [{
        'key': 'catalog_extract',
        'title': 'Извлечение характеристик',
        'description': 'Извлекает характеристики оборудования из названия позиции (ключ-значение).',
        'enabled': True,
    }])


def downgrade() -> None:
    op.execute("DELETE FROM ai_purposes WHERE key = 'catalog_extract'")
    op.drop_column('catalog_items', 'characteristics')
```

- [ ] **Step 5: ItemOut** — в `backend/app/catalog/schemas.py`, в класс `ItemOut` добавить поле (после `prices`):

```python
    characteristics: dict | None = None
```

- [ ] **Step 6: list_items** — в `backend/app/catalog/router.py`, в формировании `ItemOut(...)` внутри `list_items` добавить аргумент `characteristics=i.characteristics,` (после `prices=...`).

- [ ] **Step 7: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_catalog_characteristics.py -q`. Expected: PASS (2 теста).

- [ ] **Step 8: Commit**

```bash
git add backend/app/catalog/models.py backend/alembic/versions/f6a7b8c9d0e1_catalog_characteristics.py backend/app/catalog/schemas.py backend/app/catalog/router.py backend/tests/test_catalog_characteristics.py
git commit -m "feat(catalog): characteristics column + catalog_extract purpose + ItemOut field"
```

---

### Task 2: сервис `extract_batch`

**Files:**
- Create: `backend/app/catalog/characteristics.py`
- Test: `backend/tests/test_catalog_characteristics.py` (дополнить)

- [ ] **Step 1: Написать падающий тест** — добавить в `backend/tests/test_catalog_characteristics.py`:

```python
from app.ai import service as ai_service  # noqa: E402
from app.catalog import characteristics as ch  # noqa: E402


def test_extract_batch_sets_characteristics(db_session, monkeypatch):
    it = _item(db_session, name="Камера IP 2Мп PoE")
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {
        "items": [{"id": it.id, "characteristics": {"Разрешение": "2 Мп", "Питание": "PoE"}}]
    })
    res = ch.extract_batch(db_session, batch=40)
    assert res["processed"] == 1
    assert res["remaining"] == 0
    db_session.refresh(it)
    assert it.characteristics == {"Разрешение": "2 Мп", "Питание": "PoE"}


def test_extract_batch_marks_unanswered_as_empty(db_session, monkeypatch):
    it = _item(db_session, name="Непонятная позиция")
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {"items": []})
    res = ch.extract_batch(db_session, batch=40)
    assert res["processed"] == 1
    db_session.refresh(it)
    assert it.characteristics == {}  # обработана, но пусто — не зациклит


def test_extract_batch_empty_when_nothing_to_do(db_session, monkeypatch):
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {"items": []})
    res = ch.extract_batch(db_session, batch=40)
    assert res == {"processed": 0, "remaining": 0}
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_catalog_characteristics.py -q`. Expected: FAIL (нет модуля).

- [ ] **Step 3: Реализовать** `backend/app/catalog/characteristics.py`

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import service as ai_service
from app.catalog.models import CatalogItem

PURPOSE = "catalog_extract"

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "characteristics": {"type": "object"},
                },
                "required": ["id", "characteristics"],
            },
        }
    },
    "required": ["items"],
}


def _remaining(db: Session, supplier_id: int | None) -> int:
    q = select(func.count()).select_from(CatalogItem).where(CatalogItem.characteristics.is_(None))
    if supplier_id is not None:
        q = q.where(CatalogItem.supplier_id == supplier_id)
    return db.scalar(q) or 0


def extract_batch(db: Session, batch: int = 40, supplier_id: int | None = None) -> dict:
    """Извлекает характеристики для одной пачки позиций без characteristics.

    Возвращает {"processed": N, "remaining": M}. Позиции, по которым AI ничего не
    вернул, помечаются пустым {} (обработаны), чтобы не зациклить."""
    q = select(CatalogItem).where(CatalogItem.characteristics.is_(None))
    if supplier_id is not None:
        q = q.where(CatalogItem.supplier_id == supplier_id)
    items = list(db.scalars(q.order_by(CatalogItem.id).limit(batch)).all())
    if not items:
        return {"processed": 0, "remaining": 0}

    payload = [{"id": it.id, "name": it.name, "unit": it.unit, "kind": it.kind} for it in items]
    prompt = (
        "Ты — инженер по оборудованию. Для каждой позиции извлеки ключевые технические "
        "характеристики ИЗ НАЗВАНИЯ в виде пар ключ-значение на русском "
        "(например «Разрешение»:«2 Мп», «Питание»:«PoE», «Степень защиты»:«IP67»). "
        "Если по названию характеристик не определить — пустой объект {}. "
        "Верни строго JSON {\"items\":[{\"id\":<id>,\"characteristics\":{...}}]} по ВСЕМ позициям.\n\n"
        "ПОЗИЦИИ:\n"
        + "\n".join(f"  id={p['id']} | {p['name']} | {p['unit']} | {p['kind']}" for p in payload)
    )
    result = ai_service.call_llm(
        db, PURPOSE, [{"role": "user", "content": prompt}],
        json_schema=EXTRACT_SCHEMA, max_tokens=2000,
    )
    by_id: dict[int, dict] = {}
    if isinstance(result, dict):
        for row in result.get("items", []) or []:
            if isinstance(row, dict) and "id" in row:
                chars = row.get("characteristics")
                if isinstance(chars, dict):
                    by_id[int(row["id"])] = {str(k): str(v) for k, v in chars.items()}
    for it in items:
        it.characteristics = by_id.get(it.id, {})
    db.commit()
    return {"processed": len(items), "remaining": _remaining(db, supplier_id)}
```

- [ ] **Step 4: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_catalog_characteristics.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog/characteristics.py backend/tests/test_catalog_characteristics.py
git commit -m "feat(catalog): extract_batch AI characteristics service"
```

---

### Task 3: эндпоинт extract-characteristics

**Files:**
- Modify: `backend/app/catalog/router.py` (эндпоинт + импорты)
- Test: `backend/tests/test_catalog_characteristics.py` (дополнить)

- [ ] **Step 1: Написать падающий тест** — добавить в `backend/tests/test_catalog_characteristics.py`:

```python
from app.ai.errors import AINotConfigured  # noqa: E402
from app.auth.models import User as _User  # noqa: E402


def test_extract_endpoint_processes_and_reports(client, db_session, monkeypatch):
    a = _admin(db_session)
    it = _item(db_session, name="Камера 2Мп")
    monkeypatch.setattr(ai_service, "call_llm", lambda *args, **k: {
        "items": [{"id": it.id, "characteristics": {"Разрешение": "2 Мп"}}]})
    r = client.post("/api/catalog/extract-characteristics", headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json() == {"processed": 1, "remaining": 0}


def test_extract_endpoint_admin_only(client, db_session):
    e = _User(email="e@x.ru", name="E", role="estimator", status="active")
    db_session.add(e); db_session.commit()
    r = client.post("/api/catalog/extract-characteristics", headers=_hdr(e))
    assert r.status_code == 403


def test_extract_endpoint_503_when_not_configured(client, db_session, monkeypatch):
    a = _admin(db_session)
    _item(db_session, name="X")
    def boom(*args, **k):
        raise AINotConfigured("catalog_extract не настроена")
    monkeypatch.setattr(ai_service, "call_llm", boom)
    r = client.post("/api/catalog/extract-characteristics", headers=_hdr(a))
    assert r.status_code == 503
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_catalog_characteristics.py -q`. Expected: FAIL (404 — нет эндпоинта).

- [ ] **Step 3: Реализовать** — в `backend/app/catalog/router.py`:
  - в импортах добавить: `from app.ai.errors import AIError, AINotConfigured` и `from app.catalog import characteristics as ch_service` (рядом с `from app.catalog import importer, parser, service`).
  - добавить эндпоинт (в конец файла):

```python
@router.post(
    "/catalog/extract-characteristics", dependencies=[Depends(require_admin)]
)
def extract_characteristics(
    supplier_id: int | None = None,
    batch: int = 40,
    db: Session = Depends(get_db),
):
    try:
        return ch_service.extract_batch(db, batch=batch, supplier_id=supplier_id)
    except AINotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
```

- [ ] **Step 4: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_catalog_characteristics.py -q`. Expected: PASS.

- [ ] **Step 5: Полный backend + ruff** — `.venv\Scripts\python.exe -m pytest -q` (всё зелёное), `.venv\Scripts\ruff.exe check app/` (clean).

- [ ] **Step 6: Commit**

```bash
git add backend/app/catalog/router.py backend/tests/test_catalog_characteristics.py
git commit -m "feat(catalog): extract-characteristics admin endpoint"
```

---

### Task 4: характеристики в кандидатах ассистента

**Files:**
- Modify: `backend/app/assistant/service.py` (`_candidates`)
- Test: `backend/tests/test_assistant_service.py` (дополнить)

- [ ] **Step 1: Написать падающий тест** — добавить в `backend/tests/test_assistant_service.py`:

```python
def test_candidates_include_characteristics(db_session):
    from app.catalog.models import CatalogItem, Supplier
    sup = Supplier(name="P"); db_session.add(sup); db_session.commit()
    it = CatalogItem(supplier_id=sup.id, name="Камера", article="A", unit="шт", kind="material",
                     characteristics={"Разрешение": "2 Мп"})
    db_session.add(it); db_session.commit()
    text, items = asvc._candidates(db_session, ["камера"])
    assert "Разрешение" in text
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_service.py::test_candidates_include_characteristics -q`. Expected: FAIL.

- [ ] **Step 3: Реализовать** — в `backend/app/assistant/service.py`, в функции `_candidates`, заменить тело цикла формирования `rows`:

```python
    rows = []
    for it in items:
        work, material, _ = est_service.snapshot_line_values(db, it, None)
        price = work + material
        chars = ""
        if it.characteristics:
            pairs = ", ".join(f"{k}: {v}" for k, v in list(it.characteristics.items())[:6])
            chars = f" | {pairs}"
        rows.append(f"  {it.id} | {it.name} | {it.unit} | {it.kind} | цена {price}{chars}")
    text = "КАНДИДАТЫ КАТАЛОГА (catalog_item_id | имя | ед | вид | цена | характеристики):\n" + "\n".join(rows)
    return text, items
```

- [ ] **Step 4: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_service.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/assistant/service.py backend/tests/test_assistant_service.py
git commit -m "feat(assistant): include catalog characteristics in candidates"
```

---

### Task 5: frontend API-слой

**Files:**
- Modify: `frontend/src/api/catalog.ts`

- [ ] **Step 1: CatalogItem + функция** — в `frontend/src/api/catalog.ts`:
  - в тип `CatalogItem` добавить поле (после `prices`):

```ts
  characteristics: Record<string, string> | null;
```
  - добавить функцию (рядом с прочими экспортами, напр. после `listItems`):

```ts
export const extractCharacteristics = (supplierId?: number, batch = 40) => {
  const params = new URLSearchParams({ batch: String(batch) });
  if (supplierId != null) params.set("supplier_id", String(supplierId));
  return api<{ processed: number; remaining: number }>(
    `/catalog/extract-characteristics?${params.toString()}`,
    { method: "POST" },
  );
};
```

- [ ] **Step 2: Проверка типов** — `npm run build`. Expected: PASS (если где-то конструируется `CatalogItem` в тестах без characteristics — добавить `characteristics: null`; искать `npm run build` ошибки TS и поправить добавлением `characteristics: null`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/catalog.ts
git commit -m "feat(catalog): extractCharacteristics API + CatalogItem.characteristics"
```

---

### Task 6: ImportPage авто-извлечение после импорта

**Files:**
- Modify: `frontend/src/pages/ImportPage.tsx`

- [ ] **Step 1: Импорт + состояние** — в `frontend/src/pages/ImportPage.tsx`:
  - добавить `extractCharacteristics` в импорт из `../api/catalog`.
  - после `const [busy, setBusy] = useState(false);` добавить:

```tsx
  const [extractMsg, setExtractMsg] = useState("");
```

- [ ] **Step 2: Авто-цикл** — в функции `doImport`, после `setSummary(res); setStep("result");` (внутри `try`, перед `} catch`) вставить вызов извлечения:

```tsx
      void runExtract();
```
  и добавить функцию рядом с `doImport`:

```tsx
  async function runExtract() {
    if (supplierId === "") return;
    setExtractMsg("✨ AI: извлекаю характеристики…");
    try {
      for (let i = 0; i < 200; i++) {
        const r = await extractCharacteristics(supplierId);
        if (r.remaining <= 0) {
          setExtractMsg(r.processed > 0 || i > 0 ? "✓ Характеристики извлечены." : "");
          return;
        }
        setExtractMsg(`✨ AI: извлекаю характеристики… осталось ${r.remaining}`);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 503)
        setExtractMsg("AI не настроен — характеристики пропущены (настройте цель «catalog_extract»).");
      else setExtractMsg(err instanceof Error ? `Характеристики: ${err.message}` : "");
    }
  }
```

- [ ] **Step 3: Показать прогресс** — на шаге result, внутри `{step === "result" && summary && (` блока, после `<h2>Импорт завершён</h2>` добавить:

```tsx
            {extractMsg && <p className="text-stone-600">{extractMsg}</p>}
```

- [ ] **Step 4: Сбросить при reset** — в функции `reset()` добавить строку `setExtractMsg("");`.

- [ ] **Step 5: Проверка** — `npm run test -- src/pages/ImportPage.test.tsx` (существующие тесты ImportPage зелёные — авто-extract не должен их ломать: мок fetch в этих тестах не покрывает extract-эндпоинт, но `runExtract` ловит ошибки и не падает; если тест «creates a supplier inline» или импорт-флоу затронут — добавить в их fetch-роутер ветку `if (url.includes("extract-characteristics")) return json({processed:0, remaining:0})`). Затем `npm run build`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ImportPage.tsx frontend/src/pages/ImportPage.test.tsx
git commit -m "feat(catalog): auto-extract characteristics after import with progress"
```

---

### Task 7: CatalogPage — отображение + кнопка

**Files:**
- Modify: `frontend/src/pages/CatalogPage.tsx`

- [ ] **Step 1: Импорт + состояние** — в `frontend/src/pages/CatalogPage.tsx`:
  - добавить `extractCharacteristics` в импорт из `../api/catalog`.
  - после `const [error, setError] = useState("");` добавить:

```tsx
  const [extractMsg, setExtractMsg] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
```
  - в массив зависимостей debounce-effect (`}, [q, supplierId, kind, offset]);`) добавить `reloadKey` → `}, [q, supplierId, kind, offset, reloadKey]);`.

- [ ] **Step 2: Функция извлечения + кнопка** — добавить функцию (после `supplierName`):

```tsx
  async function runExtract() {
    setExtractMsg("✨ AI: извлекаю характеристики…");
    try {
      for (let i = 0; i < 200; i++) {
        const r = await extractCharacteristics(supplierId === "" ? undefined : supplierId);
        if (r.remaining <= 0) { setExtractMsg("✓ Готово."); break; }
        setExtractMsg(`✨ AI: извлекаю… осталось ${r.remaining}`);
      }
      setReloadKey((k) => k + 1);
    } catch (err) {
      setExtractMsg(err instanceof Error ? err.message : "Ошибка извлечения");
    }
  }
```
  - в блок фильтров (после селекта `kind`, перед закрытием `</div>` фильтров на строке с `</select>` для kind) добавить кнопку и сообщение:

```tsx
          <button
            onClick={() => void runExtract()}
            className="rounded border border-stone-700 px-3 py-1 text-stone-700"
          >
            ✨ AI: извлечь характеристики
          </button>
          {extractMsg && <span className="text-stone-500">{extractMsg}</span>}
```

- [ ] **Step 3: Колонка характеристик** — в `<thead>` после `<th>Ед.</th>` (перед `levels.map`) добавить `<th>Характеристики</th>`; в `<tbody>` строке, после `<td>{it.unit}</td>` (перед `levels.map`) добавить:

```tsx
                <td className="max-w-xs text-xs text-stone-500">
                  {it.characteristics
                    ? Object.entries(it.characteristics).slice(0, 4).map(([k, v]) => (
                        <span key={k} className="mr-1 inline-block rounded bg-stone-100 px-1">{k}: {v}</span>
                      ))
                    : ""}
                </td>
```

- [ ] **Step 4: Проверка** — `npm run test` (все зелёные; CatalogPage без отдельного теста — проверяем сборкой), `npm run build` (чисто), `npm run lint` (0 errors).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CatalogPage.tsx
git commit -m "feat(catalog): show characteristics chips + manual extract button"
```

---

## Самопроверка плана

**Покрытие спека:** модель+миграция+цель catalog_extract — Task 1 ✅; extract_batch (пачка, {} для необработанных, remaining) — Task 2 ✅; эндпоинт+403+503 — Task 3 ✅; хар-ки в кандидатах ассистента — Task 4 ✅; api-слой — Task 5 ✅; авто при импорте — Task 6 ✅; каталог отображение+кнопка — Task 7 ✅.

**Плейсхолдеры:** нет — код приведён; для существующих UI-файлов (ImportPage/CatalogPage) даны точные вставки с якорями.

**Согласованность типов:** `characteristics` — `dict|None` (бэк) / `Record<string,string>|null` (фронт); `extract_batch`/`extract_characteristics` возвращают `{processed, remaining}` = `extractCharacteristics` (фронт). Цель `PURPOSE="catalog_extract"` (Task 2) = сид миграции (Task 1) = текст 503. Миграция down_revision `e5f6a7b8c9d0` (текущий head). `call_llm(db, "catalog_extract", msgs, json_schema=, max_tokens=)` — существующая сигнатура. `_candidates` (Task 4) использует `it.characteristics` из модели (Task 1).
