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
