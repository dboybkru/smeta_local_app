# Фаза 5 — AI-ассистент редактора смет Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Агентный AI-ассистент в редакторе смет: по диалогу предлагает пакет изменений сметы (2-шаговый retrieval по каталогу), пользователь применяет одной кнопкой.

**Architecture:** Новый backend-модуль `app/assistant/` поверх `call_llm(purpose="assistant")`: `run_assistant` (шаг1 — поисковые термины, бэкенд ищет в каталоге, шаг2 — changeset) и `apply_changeset` (атомарно через модели estimates). Эндпоинты `/api/estimates/{id}/assistant/{chat,apply}`. Фронт — выезжающая `AssistantPanel` с предпросмотром changeset и кнопкой «Применить всё».

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2 (discriminated union); React 19 + TS + Vite; pytest + Vitest. Миграций НЕТ.

Рабочая папка backend: `D:\git\smeta_local_app\backend` (тесты: `.venv\Scripts\python.exe -m pytest`, линт: `.venv\Scripts\ruff.exe check app/`). Frontend: `D:\git\smeta_local_app\frontend` (`npm run test|build|lint`). Ветка `phase-5-assistant` (создана, спек закоммичен).

---

## File Structure

- `backend/app/assistant/__init__.py` — пустой пакет.
- `backend/app/assistant/schemas.py` — ChatMessage, операции (union), ChatRequest/ApplyRequest/ChatResponse, JSON-схемы.
- `backend/app/assistant/service.py` — build_context, run_assistant, apply_changeset.
- `backend/app/assistant/router.py` — chat + apply эндпоинты.
- `backend/app/estimates/service.py` — + `build_estimate_detail` (рефактор из router.get_estimate).
- `backend/app/estimates/router.py` — get_estimate использует `build_estimate_detail`.
- `backend/app/main.py` — регистрация assistant_router.
- `backend/tests/test_assistant_service.py`, `test_assistant_api.py` — тесты.
- `frontend/src/api/assistant.ts` — типы + chatAssistant/applyChangeset.
- `frontend/src/components/estimate/AssistantPanel.tsx` (+ `.test.tsx`).
- `frontend/src/pages/EstimateEditorPage.tsx` — кнопка + панель.

---

### Task 1: assistant schemas (операции changeset)

**Files:**
- Create: `backend/app/assistant/__init__.py` (пустой)
- Create: `backend/app/assistant/schemas.py`
- Test: `backend/tests/test_assistant_service.py`

- [ ] **Step 1: Создать пустой** `backend/app/assistant/__init__.py` (0 байт).

- [ ] **Step 2: Написать падающий тест** `backend/tests/test_assistant_service.py`

```python
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.assistant import schemas


def test_operation_union_discriminates_by_op():
    adapter = TypeAdapter(schemas.Operation)
    add = adapter.validate_python({"op": "add_section", "name": "Оборудование"})
    assert isinstance(add, schemas.AddSection)
    line = adapter.validate_python(
        {"op": "add_catalog_line", "section_name": "Оборудование", "catalog_item_id": 5, "qty": "2"}
    )
    assert isinstance(line, schemas.AddCatalogLine)
    assert line.qty == Decimal("2")
    with pytest.raises(ValidationError):
        adapter.validate_python({"op": "nope"})
```

- [ ] **Step 3: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_service.py -q`. Expected: FAIL (нет модуля).

- [ ] **Step 4: Реализовать** `backend/app/assistant/schemas.py`

```python
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# --- chat ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


# --- операции changeset ---
class AddSection(BaseModel):
    op: Literal["add_section"]
    name: str


class AddCatalogLine(BaseModel):
    op: Literal["add_catalog_line"]
    section_name: str
    catalog_item_id: int
    qty: Decimal = Decimal("1")


class AddCustomLine(BaseModel):
    op: Literal["add_custom_line"]
    section_name: str
    name: str
    unit: str = "шт"
    qty: Decimal = Decimal("1")
    material_price: Decimal = Decimal("0")
    work_price: Decimal = Decimal("0")


class SetQty(BaseModel):
    op: Literal["set_qty"]
    line_id: int
    qty: Decimal


class SetPrice(BaseModel):
    op: Literal["set_price"]
    line_id: int
    material_price: Decimal | None = None
    work_price: Decimal | None = None


class DeleteLine(BaseModel):
    op: Literal["delete_line"]
    line_id: int


class DeleteSection(BaseModel):
    op: Literal["delete_section"]
    section_id: int


class SetSectionMarkup(BaseModel):
    op: Literal["set_section_markup"]
    section_id: int
    markup_percent: Decimal


class SetVat(BaseModel):
    op: Literal["set_vat"]
    vat_enabled: bool
    vat_rate: Decimal | None = None


Operation = Annotated[
    Union[
        AddSection, AddCatalogLine, AddCustomLine, SetQty, SetPrice,
        DeleteLine, DeleteSection, SetSectionMarkup, SetVat,
    ],
    Field(discriminator="op"),
]


class ApplyRequest(BaseModel):
    operations: list[Operation]


class ChatResponse(BaseModel):
    reply: str
    operations: list[Operation]


# --- JSON-схемы для call_llm (встраиваются как текст-подсказка) ---
SEARCH_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
}

CHANGESET_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "operations": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["reply", "operations"],
}
```

- [ ] **Step 5: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_service.py -q`. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/assistant/__init__.py backend/app/assistant/schemas.py backend/tests/test_assistant_service.py
git commit -m "feat(phase5): assistant schemas (changeset operations)"
```

---

### Task 2: рефактор `build_estimate_detail`

**Files:**
- Modify: `backend/app/estimates/service.py` (добавить функцию)
- Modify: `backend/app/estimates/router.py:65-87` (использовать функцию)
- Test: `backend/tests/test_estimate_detail.py` (существующие тесты должны остаться зелёными)

- [ ] **Step 1: Добавить функцию в** `backend/app/estimates/service.py` (в конец файла; нужен импорт схем — добавить `from app.estimates import schemas` если его нет, иначе использовать существующий):

```python
def build_estimate_detail(est: models.Estimate, user: User) -> "schemas.EstimateDetail":
    """Деталь сметы с роле-зависимым сокрытием маржи/закупки (общий код для get/apply)."""
    can_see_margin = user.role == "admin" or est.owner_id == user.id
    totals = compute_totals(est)
    if not can_see_margin:
        for s in totals["sections"]:
            s["purchase"] = None
            s["margin"] = None
        totals["purchase"] = None
        totals["margin"] = None
    detail = schemas.EstimateDetail.model_validate(est)
    detail.totals = schemas.EstimateTotals(**totals)
    if not can_see_margin:
        for branch in detail.branches:
            for section in branch.sections:
                for line in section.lines:
                    line.purchase_price_snapshot = None
    return detail
```

Добавить наверх файла, если отсутствуют, импорты: `from app.auth.models import User` и `from app.estimates import schemas`. (Проверить шапку `service.py` — если `models` импортируется как `from app.estimates import models`, добавить `schemas` в тот же импорт: `from app.estimates import models, schemas`.)

- [ ] **Step 2: Использовать в** `backend/app/estimates/router.py` — заменить тело `get_estimate` (строки ~69-87) на:

```python
    est = service.get_owned_estimate(db, estimate_id, user)
    return service.build_estimate_detail(est, user)
```

- [ ] **Step 3: Запустить существующие тесты** — `.venv\Scripts\python.exe -m pytest tests/test_estimate_detail.py -q`. Expected: PASS (5+ тестов; поведение не изменилось).

- [ ] **Step 4: Commit**

```bash
git add backend/app/estimates/service.py backend/app/estimates/router.py
git commit -m "refactor(estimates): extract build_estimate_detail for reuse"
```

---

### Task 3: `run_assistant` (2-шаговый retrieval)

**Files:**
- Create: `backend/app/assistant/service.py`
- Test: `backend/tests/test_assistant_service.py` (дополнить)

- [ ] **Step 1: Написать падающий тест** — добавить в `backend/tests/test_assistant_service.py`:

```python
from app.assistant import service as asvc  # noqa: E402
from app.ai import service as ai_service  # noqa: E402


def _estimate_with_catalog(db_session):
    from app.auth.models import User
    from app.catalog.models import CatalogItem, Supplier
    from app.estimates import models as em
    u = User(email="a@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    sup = Supplier(name="P"); db_session.add(sup); db_session.commit()
    item = CatalogItem(supplier_id=sup.id, name="Камера IP", article="A", unit="шт", kind="material")
    db_session.add(item); db_session.commit()
    est = em.Estimate(owner_id=u.id, object_name="Склад")
    db_session.add(est); db_session.commit()
    br = em.EstimateBranch(estimate_id=est.id, name="Базовая")
    db_session.add(br); db_session.commit()
    db_session.refresh(est)
    return est, item


def test_run_assistant_two_step(db_session, monkeypatch):
    est, item = _estimate_with_catalog(db_session)
    calls = [
        {"queries": ["камера"]},  # шаг 1
        {"reply": "Добавил камеру.", "operations": [
            {"op": "add_section", "name": "Оборудование"},
            {"op": "add_catalog_line", "section_name": "Оборудование",
             "catalog_item_id": item.id, "qty": "2"},
        ]},  # шаг 2
    ]
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: calls.pop(0))
    out = asvc.run_assistant(db_session, est, [schemas.ChatMessage(role="user", content="добавь камеру")])
    assert out.reply == "Добавил камеру."
    assert len(out.operations) == 2
    assert isinstance(out.operations[1], schemas.AddCatalogLine)


def test_run_assistant_skips_invalid_ops(db_session, monkeypatch):
    est, _ = _estimate_with_catalog(db_session)
    calls = [
        {"queries": []},
        {"reply": "ок", "operations": [
            {"op": "add_section", "name": "Раздел"},
            {"op": "garbage"},  # невалидная — пропускается
        ]},
    ]
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: calls.pop(0))
    out = asvc.run_assistant(db_session, est, [schemas.ChatMessage(role="user", content="hi")])
    assert len(out.operations) == 1
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_service.py -q`. Expected: FAIL (нет service).

- [ ] **Step 3: Реализовать** `backend/app/assistant/service.py`

```python
from decimal import Decimal

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.ai import service as ai_service
from app.assistant import schemas
from app.catalog import service as catalog_service
from app.catalog.models import CatalogItem
from app.estimates import models as em
from app.estimates import service as est_service

_OP_ADAPTER = TypeAdapter(schemas.Operation)
_MAX_QUERIES = 5
_MAX_CANDIDATES = 30
_MAX_TOKENS = 1500


def build_context(estimate: em.Estimate) -> str:
    lines: list[str] = [
        f"Смета #{estimate.id}: {estimate.object_name or '(без названия)'}; "
        f"НДС {'вкл ' + str(estimate.vat_rate) + '%' if estimate.vat_enabled else 'выкл'}."
    ]
    branch = est_service.base_branch(estimate)
    for s in branch.sections:
        lines.append(f"Раздел #{s.id} «{s.name}» (наценка {s.markup_percent}%):")
        for ln in s.lines:
            lines.append(
                f"  строка #{ln.id}: {ln.name} | {ln.qty} {ln.unit} | "
                f"мат {ln.material_price} / раб {ln.work_price}"
            )
    if len(lines) == 1:
        lines.append("(смета пустая)")
    return "\n".join(lines)


def _candidates(db: Session, queries: list[str]) -> tuple[str, list[CatalogItem]]:
    seen: dict[int, CatalogItem] = {}
    for q in (queries or [])[:_MAX_QUERIES]:
        items, _ = catalog_service.search_items(db, q=q, limit=5)
        for it in items:
            seen[it.id] = it
            if len(seen) >= _MAX_CANDIDATES:
                break
        if len(seen) >= _MAX_CANDIDATES:
            break
    items = list(seen.values())
    if not items:
        return "(каталог: подходящих позиций не найдено)", items
    text = "КАНДИДАТЫ КАТАЛОГА (id | имя | ед | вид):\n" + "\n".join(
        f"  {it.id} | {it.name} | {it.unit} | {it.kind}" for it in items
    )
    return text, items


def _parse_ops(raw: object) -> list:
    out = []
    if not isinstance(raw, list):
        return out
    for r in raw:
        try:
            out.append(_OP_ADAPTER.validate_python(r))
        except ValidationError:
            continue
    return out


def run_assistant(
    db: Session, estimate: em.Estimate, messages: list[schemas.ChatMessage]
) -> schemas.ChatResponse:
    context = build_context(estimate)
    convo = [{"role": m.role, "content": m.content} for m in messages]

    # Шаг 1 — поисковые термины
    search_prompt = (
        "Ты помощник по сметам. По последнему сообщению пользователя и смете предложи "
        "до 5 коротких поисковых запросов по каталогу материалов/работ, которые помогут "
        "выполнить просьбу. Если каталог не нужен (вопрос/правка существующего) — пустой список.\n\n"
        f"СМЕТА:\n{context}"
    )
    step1 = ai_service.call_llm(
        db, "assistant",
        [{"role": "system", "content": search_prompt}, *convo],
        json_schema=schemas.SEARCH_SCHEMA, max_tokens=_MAX_TOKENS,
    )
    queries = step1.get("queries", []) if isinstance(step1, dict) else []

    cand_text, _ = _candidates(db, queries)

    # Шаг 2 — changeset
    ops_prompt = (
        "Ты агент-редактор сметы. Сформируй изменения сметы под просьбу пользователя.\n"
        "Доступные операции (поле op): add_section{name}; "
        "add_catalog_line{section_name, catalog_item_id, qty}; "
        "add_custom_line{section_name, name, unit, qty, material_price, work_price}; "
        "set_qty{line_id, qty}; set_price{line_id, material_price?, work_price?}; "
        "delete_line{line_id}; delete_section{section_id}; "
        "set_section_markup{section_id, markup_percent}; set_vat{vat_enabled, vat_rate?}.\n"
        "Правила: ссылайся ТОЛЬКО на реальные id из СМЕТЫ и КАНДИДАТОВ. Раздел указывай по имени "
        "(section_name) — можешь создать раздел add_section и в том же пакете добавлять в него строки. "
        "Если изменения не нужны — пустой operations. В reply кратко по-русски опиши, что предлагаешь.\n\n"
        f"СМЕТА:\n{context}\n\n{cand_text}"
    )
    step2 = ai_service.call_llm(
        db, "assistant",
        [{"role": "system", "content": ops_prompt}, *convo],
        json_schema=schemas.CHANGESET_SCHEMA, max_tokens=_MAX_TOKENS,
    )
    reply = step2.get("reply", "") if isinstance(step2, dict) else ""
    operations = _parse_ops(step2.get("operations") if isinstance(step2, dict) else None)
    return schemas.ChatResponse(reply=reply, operations=operations)
```

- [ ] **Step 4: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_service.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/assistant/service.py backend/tests/test_assistant_service.py
git commit -m "feat(phase5): run_assistant two-step retrieval pipeline"
```

---

### Task 4: `apply_changeset` (атомарное применение)

**Files:**
- Modify: `backend/app/assistant/service.py` (добавить функцию)
- Test: `backend/tests/test_assistant_service.py` (дополнить)

- [ ] **Step 1: Написать падающий тест** — добавить в `backend/tests/test_assistant_service.py`:

```python
def test_apply_changeset_add_section_and_catalog_line(db_session):
    est, item = _estimate_with_catalog(db_session)
    ops = [
        schemas.AddSection(op="add_section", name="Оборудование"),
        schemas.AddCatalogLine(op="add_catalog_line", section_name="Оборудование",
                               catalog_item_id=item.id, qty=Decimal("3")),
    ]
    asvc.apply_changeset(db_session, est, ops)
    db_session.refresh(est)
    branch = est.branches[0]
    assert len(branch.sections) == 1
    sec = branch.sections[0]
    assert sec.name == "Оборудование"
    assert len(sec.lines) == 1
    assert sec.lines[0].qty == Decimal("3")
    assert sec.lines[0].item_id == item.id


def test_apply_changeset_set_qty_and_delete(db_session):
    from app.estimates import models as em
    est, item = _estimate_with_catalog(db_session)
    sec = em.EstimateSection(branch_id=est.branches[0].id, name="С", sort_order=0)
    db_session.add(sec); db_session.commit()
    ln = em.EstimateLine(section_id=sec.id, name="X", unit="шт", qty=Decimal("1"))
    db_session.add(ln); db_session.commit()
    asvc.apply_changeset(db_session, est, [
        schemas.SetQty(op="set_qty", line_id=ln.id, qty=Decimal("5")),
    ])
    db_session.refresh(ln)
    assert ln.qty == Decimal("5")
    asvc.apply_changeset(db_session, est, [
        schemas.DeleteLine(op="delete_line", line_id=ln.id),
    ])
    db_session.refresh(sec)
    assert len(sec.lines) == 0


def test_apply_changeset_atomic_rollback_on_bad_ref(db_session):
    from app.estimates import models as em
    est, item = _estimate_with_catalog(db_session)
    # add_section валиден, set_qty на чужой line_id (999) — должно откатить ВЕСЬ пакет
    with pytest.raises(Exception):
        asvc.apply_changeset(db_session, est, [
            schemas.AddSection(op="add_section", name="Новый"),
            schemas.SetQty(op="set_qty", line_id=999, qty=Decimal("2")),
        ])
    db_session.rollback()
    db_session.refresh(est)
    assert len(est.branches[0].sections) == 0  # раздел не создан (откат)
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_service.py -q`. Expected: FAIL (нет apply_changeset).

- [ ] **Step 3: Реализовать** — добавить в `backend/app/assistant/service.py`:

```python
class ApplyError(Exception):
    pass


def _line_in(estimate: em.Estimate, line_id: int) -> em.EstimateLine:
    for br in estimate.branches:
        for s in br.sections:
            for ln in s.lines:
                if ln.id == line_id:
                    return ln
    raise ApplyError(f"Строка #{line_id} не принадлежит смете")


def _section_in(estimate: em.Estimate, section_id: int) -> em.EstimateSection:
    for br in estimate.branches:
        for s in br.sections:
            if s.id == section_id:
                return s
    raise ApplyError(f"Раздел #{section_id} не принадлежит смете")


def apply_changeset(db: Session, estimate: em.Estimate, operations: list) -> None:
    """Атомарно применяет операции к смете. При любой ошибке — откат всего пакета."""
    branch = est_service.base_branch(estimate)
    client = db.get(em.Client, estimate.client_id) if estimate.client_id else None
    # карта имя→раздел: существующие + созданные в этом пакете
    by_name: dict[str, em.EstimateSection] = {s.name: s for s in branch.sections}
    section_order = len(branch.sections)
    try:
        # 1) создать новые разделы первыми
        for op in operations:
            if isinstance(op, schemas.AddSection):
                sec = em.EstimateSection(
                    branch_id=branch.id, name=op.name, sort_order=section_order
                )
                section_order += 1
                db.add(sec)
                by_name[op.name] = sec
        db.flush()  # назначить id новым разделам (autoflush=False)

        # 2) остальные операции
        for op in operations:
            if isinstance(op, schemas.AddSection):
                continue
            if isinstance(op, schemas.AddCatalogLine):
                sec = by_name.get(op.section_name)
                if sec is None:
                    raise ApplyError(f"Раздел «{op.section_name}» не найден")
                item = db.get(CatalogItem, op.catalog_item_id)
                if item is None:
                    raise ApplyError(f"Позиция каталога #{op.catalog_item_id} не найдена")
                work, material, purchase = est_service.snapshot_line_values(db, item, client)
                db.add(em.EstimateLine(
                    section_id=sec.id, item_id=item.id, name=item.name, unit=item.unit,
                    qty=op.qty, work_price=work, material_price=material,
                    purchase_price_snapshot=purchase, sort_order=len(sec.lines),
                ))
            elif isinstance(op, schemas.AddCustomLine):
                sec = by_name.get(op.section_name)
                if sec is None:
                    raise ApplyError(f"Раздел «{op.section_name}» не найден")
                db.add(em.EstimateLine(
                    section_id=sec.id, name=op.name, unit=op.unit, qty=op.qty,
                    work_price=op.work_price, material_price=op.material_price,
                    sort_order=len(sec.lines),
                ))
            elif isinstance(op, schemas.SetQty):
                _line_in(estimate, op.line_id).qty = op.qty
            elif isinstance(op, schemas.SetPrice):
                ln = _line_in(estimate, op.line_id)
                if op.material_price is not None:
                    ln.material_price = op.material_price
                if op.work_price is not None:
                    ln.work_price = op.work_price
            elif isinstance(op, schemas.DeleteLine):
                db.delete(_line_in(estimate, op.line_id))
            elif isinstance(op, schemas.DeleteSection):
                db.delete(_section_in(estimate, op.section_id))
            elif isinstance(op, schemas.SetSectionMarkup):
                _section_in(estimate, op.section_id).markup_percent = op.markup_percent
            elif isinstance(op, schemas.SetVat):
                estimate.vat_enabled = op.vat_enabled
                if op.vat_rate is not None:
                    estimate.vat_rate = op.vat_rate
        db.commit()
    except Exception:
        db.rollback()
        raise
```

- [ ] **Step 4: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_service.py -q`. Expected: PASS (все тесты файла).

- [ ] **Step 5: Commit**

```bash
git add backend/app/assistant/service.py backend/tests/test_assistant_service.py
git commit -m "feat(phase5): apply_changeset atomic estimate mutations"
```

---

### Task 5: assistant router (chat + apply) + регистрация

**Files:**
- Create: `backend/app/assistant/router.py`
- Modify: `backend/app/main.py` (регистрация)
- Test: `backend/tests/test_assistant_api.py`

- [ ] **Step 1: Написать падающий тест** `backend/tests/test_assistant_api.py`

```python
from decimal import Decimal

from app.ai import service as ai_service
from app.auth.models import User
from app.catalog.models import CatalogItem, Supplier
from app.core.security import create_access_token
from app.estimates import models as em


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _setup(db_session, role="estimator"):
    u = User(email=f"{role}@x.ru", name="U", role=role, status="active")
    db_session.add(u); db_session.commit()
    sup = Supplier(name="P"); db_session.add(sup); db_session.commit()
    item = CatalogItem(supplier_id=sup.id, name="Камера", article="A", unit="шт", kind="material")
    db_session.add(item); db_session.commit()
    est = em.Estimate(owner_id=u.id, object_name="O")
    db_session.add(est); db_session.commit()
    db_session.add(em.EstimateBranch(estimate_id=est.id, name="Базовая")); db_session.commit()
    db_session.refresh(est)
    return u, est, item


def test_chat_returns_reply_and_operations(client, db_session, monkeypatch):
    u, est, item = _setup(db_session)
    calls = [
        {"queries": ["камера"]},
        {"reply": "ок", "operations": [{"op": "add_section", "name": "Обор"}]},
    ]
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: calls.pop(0))
    r = client.post(f"/api/estimates/{est.id}/assistant/chat", headers=_hdr(u),
                    json={"messages": [{"role": "user", "content": "добавь раздел"}]})
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "ок"
    assert r.json()["operations"][0]["op"] == "add_section"


def test_apply_mutates_and_returns_detail(client, db_session):
    u, est, item = _setup(db_session)
    r = client.post(f"/api/estimates/{est.id}/assistant/apply", headers=_hdr(u),
                    json={"operations": [
                        {"op": "add_section", "name": "Оборудование"},
                        {"op": "add_catalog_line", "section_name": "Оборудование",
                         "catalog_item_id": item.id, "qty": "2"},
                    ]})
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["branches"][0]["sections"][0]["name"] == "Оборудование"
    assert detail["branches"][0]["sections"][0]["lines"][0]["qty"] == "2.000"


def test_viewer_cannot_use_assistant(client, db_session):
    u, est, item = _setup(db_session)
    viewer = User(email="v@x.ru", name="V", role="viewer", status="active")
    db_session.add(viewer); db_session.commit()
    r = client.post(f"/api/estimates/{est.id}/assistant/apply", headers=_hdr(viewer),
                    json={"operations": []})
    assert r.status_code == 403


def test_chat_503_when_ai_not_configured(client, db_session, monkeypatch):
    from app.ai.errors import AINotConfigured
    u, est, item = _setup(db_session)
    def boom(*a, **k):
        raise AINotConfigured("не настроен")
    monkeypatch.setattr(ai_service, "call_llm", boom)
    r = client.post(f"/api/estimates/{est.id}/assistant/chat", headers=_hdr(u),
                    json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503
```

- [ ] **Step 2: Запустить — упадёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_api.py -q`. Expected: FAIL (404, роутера нет).

- [ ] **Step 3: Реализовать** `backend/app/assistant/router.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.errors import AIError, AINotConfigured
from app.assistant import schemas, service
from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import schemas as est_schemas
from app.estimates import service as est_service

router = APIRouter(prefix="/api", tags=["assistant"])


@router.post("/estimates/{estimate_id}/assistant/chat", response_model=schemas.ChatResponse)
def assistant_chat(
    estimate_id: int,
    body: schemas.ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    try:
        return service.run_assistant(db, est, body.messages)
    except AINotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post(
    "/estimates/{estimate_id}/assistant/apply",
    response_model=est_schemas.EstimateDetail,
)
def assistant_apply(
    estimate_id: int,
    body: schemas.ApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    try:
        service.apply_changeset(db, est, body.operations)
    except service.ApplyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.refresh(est)
    return est_service.build_estimate_detail(est, user)
```

- [ ] **Step 4: Зарегистрировать в** `backend/app/main.py` — добавить импорт `from app.assistant.router import router as assistant_router` (рядом с прочими) и `app.include_router(assistant_router)` (после `estimates_router`).

- [ ] **Step 5: Запустить — пройдёт** — `.venv\Scripts\python.exe -m pytest tests/test_assistant_api.py -q`. Expected: PASS (4 теста).

- [ ] **Step 6: Полный backend + ruff** — `.venv\Scripts\python.exe -m pytest -q` (всё зелёное), `.venv\Scripts\ruff.exe check app/` (All checks passed).

- [ ] **Step 7: Commit**

```bash
git add backend/app/assistant/router.py backend/app/main.py backend/tests/test_assistant_api.py
git commit -m "feat(phase5): assistant chat + apply endpoints"
```

---

### Task 6: frontend API-слой `api/assistant.ts`

**Files:**
- Create: `frontend/src/api/assistant.ts`

- [ ] **Step 1: Создать** `frontend/src/api/assistant.ts`

```ts
import { api } from "./client";
import type { EstimateDetail } from "./estimates";

export type ChatMessage = { role: "user" | "assistant"; content: string };

// Операции changeset — поле op дискриминатор; остальные поля зависят от op.
export type Operation = {
  op: string;
  name?: string;
  section_name?: string;
  catalog_item_id?: number;
  qty?: string;
  unit?: string;
  material_price?: string | null;
  work_price?: string | null;
  line_id?: number;
  section_id?: number;
  markup_percent?: string;
  vat_enabled?: boolean;
  vat_rate?: string | null;
};

export type ChatResponse = { reply: string; operations: Operation[] };

export function chatAssistant(estimateId: number, messages: ChatMessage[]) {
  return api<ChatResponse>(`/estimates/${estimateId}/assistant/chat`, {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
}

export function applyChangeset(estimateId: number, operations: Operation[]) {
  return api<EstimateDetail>(`/estimates/${estimateId}/assistant/apply`, {
    method: "POST",
    body: JSON.stringify({ operations }),
  });
}
```

- [ ] **Step 2: Проверка типов** — `npm run build`. Expected: PASS (если `EstimateDetail` не экспортируется из `api/estimates.ts` — добавить `export` к его типу).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/assistant.ts
git commit -m "feat(phase5): assistant API client"
```

---

### Task 7: `AssistantPanel` (чат + предпросмотр changeset)

**Files:**
- Create: `frontend/src/components/estimate/AssistantPanel.tsx`
- Test: `frontend/src/components/estimate/AssistantPanel.test.tsx`

- [ ] **Step 1: Написать падающий тест** `frontend/src/components/estimate/AssistantPanel.test.tsx`

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AssistantPanel from "./AssistantPanel";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("AssistantPanel", () => {
  it("sends a message, shows reply + changeset, applies it", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/assistant/chat"))
        return json({ reply: "Добавил раздел", operations: [{ op: "add_section", name: "Обор" }] });
      if (url.includes("/assistant/apply"))
        return json({ id: 1, branches: [], totals: null });
      return json({});
    });
    vi.stubGlobal("fetch", f);
    const onApplied = vi.fn();
    render(<AssistantPanel estimateId={1} onApplied={onApplied} onClose={() => {}} />);
    await userEvent.type(screen.getByLabelText("Сообщение ассистенту"), "добавь раздел");
    await userEvent.click(screen.getByText("Отправить"));
    expect(await screen.findByText("Добавил раздел")).toBeInTheDocument();
    expect(screen.getByText(/Раздел/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Применить всё"));
    expect(onApplied).toHaveBeenCalled();
    const applies = f.mock.calls.filter((c) => String(c[0]).includes("/assistant/apply"));
    expect(applies.length).toBe(1);
  });

  it("shows 'AI not configured' on 503", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "не настроен" }, 503)));
    render(<AssistantPanel estimateId={1} onApplied={() => {}} onClose={() => {}} />);
    await userEvent.type(screen.getByLabelText("Сообщение ассистенту"), "hi");
    await userEvent.click(screen.getByText("Отправить"));
    expect(await screen.findByText(/AI не настроен/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Запустить — упадёт** — `npm run test -- src/components/estimate/AssistantPanel.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Реализовать** `frontend/src/components/estimate/AssistantPanel.tsx`

```tsx
import { useState } from "react";
import { ApiError } from "../../api/client";
import {
  applyChangeset, chatAssistant,
  type ChatMessage, type Operation,
} from "../../api/assistant";
import type { EstimateDetail } from "../../api/estimates";

function opLabel(o: Operation): string {
  switch (o.op) {
    case "add_section": return `➕ Раздел «${o.name}»`;
    case "add_catalog_line": return `➕ Позиция #${o.catalog_item_id} ×${o.qty} в «${o.section_name}»`;
    case "add_custom_line": return `➕ «${o.name}» ×${o.qty} ${o.unit ?? ""} в «${o.section_name}»`;
    case "set_qty": return `✏️ кол-во строки #${o.line_id} → ${o.qty}`;
    case "set_price": return `✏️ цена строки #${o.line_id}`;
    case "delete_line": return `🗑 удалить строку #${o.line_id}`;
    case "delete_section": return `🗑 удалить раздел #${o.section_id}`;
    case "set_section_markup": return `✏️ наценка раздела #${o.section_id} → ${o.markup_percent}%`;
    case "set_vat": return `✏️ НДС ${o.vat_enabled ? "вкл" : "выкл"}${o.vat_rate ? " " + o.vat_rate + "%" : ""}`;
    default: return o.op;
  }
}

export default function AssistantPanel({
  estimateId, onApplied, onClose,
}: {
  estimateId: number;
  onApplied: (d: EstimateDetail) => void;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Operation[]>([]);
  const [busy, setBusy] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);
  const [error, setError] = useState("");

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;
    const next = [...messages, { role: "user" as const, content: text }];
    setMessages(next); setDraft(""); setPending([]); setError(""); setNotConfigured(false);
    setBusy(true);
    try {
      const out = await chatAssistant(estimateId, next);
      setMessages((m) => [...m, { role: "assistant", content: out.reply }]);
      setPending(out.operations);
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) setNotConfigured(true);
      else setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    setError("");
    try {
      const detail = await applyChangeset(estimateId, pending);
      setPending([]);
      setMessages((m) => [...m, { role: "assistant", content: "✓ Изменения применены." }]);
      onApplied(detail);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка применения");
    }
  }

  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-[420px] flex-col border-l border-stone-200 bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-stone-200 px-4 py-3">
        <h2 className="font-serif text-lg text-stone-900">✨ Ассистент</h2>
        <button onClick={onClose} aria-label="Закрыть" className="text-stone-500 hover:text-stone-900">✕</button>
      </div>

      <div className="flex-1 space-y-3 overflow-auto p-4 text-sm">
        {messages.length === 0 && (
          <p className="text-stone-400">Опишите, что добавить или изменить в смете — например «добавь видеонаблюдение склада».</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-stone-900" : "text-stone-600"}>
            <span className="mr-1 text-xs text-stone-400">{m.role === "user" ? "Вы:" : "AI:"}</span>{m.content}
          </div>
        ))}
        {busy && <p className="text-stone-400">Думаю…</p>}
        {notConfigured && (
          <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
            ⚠ AI не настроен — попросите администратора подключить провайдера в «AI».
          </div>
        )}
        {error && <p role="alert" className="text-red-600">{error}</p>}

        {pending.length > 0 && (
          <div className="rounded border border-stone-300 bg-stone-50 p-3">
            <p className="mb-2 font-medium text-stone-700">Предложенные изменения:</p>
            <ul className="mb-3 space-y-1">
              {pending.map((o, i) => <li key={i}>{opLabel(o)}</li>)}
            </ul>
            <div className="flex gap-2">
              <button onClick={() => void apply()} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Применить всё</button>
              <button onClick={() => setPending([])} className="text-stone-500">Отклонить</button>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-stone-200 p-3">
        <textarea
          aria-label="Сообщение ассистенту"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          placeholder="Сообщение…"
          className="mb-2 w-full rounded border border-stone-300 px-2 py-1"
        />
        <button onClick={() => void send()} disabled={busy}
          className="rounded border border-stone-700 px-4 py-1.5 text-stone-700 disabled:opacity-50">
          Отправить
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Запустить — пройдёт** — `npm run test -- src/components/estimate/AssistantPanel.test.tsx`. Expected: PASS (2 теста).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/estimate/AssistantPanel.tsx frontend/src/components/estimate/AssistantPanel.test.tsx
git commit -m "feat(phase5): AssistantPanel chat + changeset preview"
```

---

### Task 8: интеграция в `EstimateEditorPage`

**Files:**
- Modify: `frontend/src/pages/EstimateEditorPage.tsx`

- [ ] **Step 1: Подключить панель** — в `frontend/src/pages/EstimateEditorPage.tsx`:
  - добавить импорт: `import AssistantPanel from "../components/estimate/AssistantPanel";`
  - после `const [newSection, setNewSection] = useState("");` добавить: `const [assistantOpen, setAssistantOpen] = useState(false);`
  - заменить блок `return ( <Shell> … </Shell> );` так, чтобы в конце `<Shell>` (после `<EstimateTabs .../>`) добавить кнопку и панель:

```tsx
  return (
    <Shell>
      {e.error && <p role="alert" className="mb-3 text-red-600">{e.error}</p>}
      <EstimateHeader key={est.id} estimate={est} clients={clients} canEdit={e.canEdit} onPatch={e.patchEstimate} onCreateClient={handleCreateClient} />
      <EstimateTabs
        smeta={smetaTab}
        kp={<ProposalTab estimateId={est.id} initial={est.proposal} canEdit={e.canEdit} />}
        share={<ShareTab estimateId={est.id} canEdit={e.canEdit} />}
      />
      {e.canEdit && !assistantOpen && (
        <button
          onClick={() => setAssistantOpen(true)}
          className="fixed bottom-6 right-6 z-30 rounded-full border border-stone-700 bg-white px-4 py-2 text-stone-700 shadow-lg"
        >
          ✨ Ассистент
        </button>
      )}
      {e.canEdit && assistantOpen && (
        <AssistantPanel
          estimateId={est.id}
          onApplied={() => void e.reload()}
          onClose={() => setAssistantOpen(false)}
        />
      )}
    </Shell>
  );
```

- [ ] **Step 2: Полный прогон фронта** — `npm run test` (все зелёные), `npm run build` (чисто), `npm run lint` (0 errors; warnings set-state-in-effect допустимы).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/EstimateEditorPage.tsx
git commit -m "feat(phase5): wire assistant panel into estimate editor"
```

---

## Самопроверка плана

**Покрытие спека:** schemas+операции — Task 1 ✅; build_estimate_detail рефактор — Task 2 ✅; run_assistant 2-шаг — Task 3 ✅; apply_changeset атомарно+все операции — Task 4 ✅; chat/apply эндпоинты+403/503+регистрация — Task 5 ✅; api-слой — Task 6 ✅; AssistantPanel чат+предпросмотр+apply+503 — Task 7 ✅; кнопка+панель+reload в редакторе — Task 8 ✅. Миграций нет (эфемерный диалог) — соответствует спеку.

**Плейсхолдеры:** нет — весь код приведён.

**Согласованность типов:** `Operation`-union (поле `op`) одинаков в schemas (Task 1), service.apply (`isinstance`, Task 4), api/assistant.ts (Task 6), AssistantPanel (Task 7). `run_assistant`/`apply_changeset`/`build_estimate_detail`/`ApplyError` определены в Task 2-4 и используются в Task 5 теми же именами. `chatAssistant`/`applyChangeset` (Task 6) ↔ AssistantPanel (Task 7). `call_llm(db,"assistant",messages,json_schema=,max_tokens=)` — существующая сигнатура. `snapshot_line_values`/`base_branch`/`get_owned_estimate`/`require_write`/`search_items` — существующие. autoflush=False учтён (`db.flush()` после создания разделов в apply_changeset).
