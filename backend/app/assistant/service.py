from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import service as ai_service
from app.assistant import schemas
from app.assistant.models import AssistantMessage
from app.catalog import service as catalog_service
from app.catalog.models import CatalogItem
from app.estimates import models as em
from app.estimates import service as est_service

_OP_ADAPTER = TypeAdapter(schemas.Operation)
_MAX_QUERIES = 5
_MAX_CANDIDATES = 40
_PER_QUERY = 15
_MAX_TOKENS = 1500


def load_history(db: Session, estimate_id: int) -> list[schemas.ChatMessage]:
    rows = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.estimate_id == estimate_id)
        .order_by(AssistantMessage.id)
    ).all()
    return [schemas.ChatMessage(role=r.role, content=r.content) for r in rows]


def save_message(db: Session, estimate_id: int, role: str, content: str) -> None:
    db.add(AssistantMessage(estimate_id=estimate_id, role=role, content=content))
    db.commit()


def build_context(estimate: em.Estimate) -> str:
    totals = est_service.compute_totals(estimate)
    sec_totals = {s["section_id"]: s for s in totals["sections"]}
    nds = f"вкл {estimate.vat_rate}%" if estimate.vat_enabled else "выкл"
    margin = totals.get("margin")
    lines: list[str] = [
        f"Смета #{estimate.id}: {estimate.object_name or '(без названия)'}; НДС {nds}.",
        f"ИТОГО: материалы {totals['materials']}, работы {totals['works']}, "
        f"без НДС {totals['subtotal']}, НДС {totals['vat']}, ВСЕГО {totals['total']}"
        + (f", маржа {margin}" if margin is not None else "") + ".",
    ]
    branch = est_service.base_branch(estimate)
    for s in branch.sections:
        st = sec_totals.get(s.id, {})
        lines.append(
            f"Раздел #{s.id} «{s.name}» (наценка {s.markup_percent}%; "
            f"итог раздела {st.get('total', '?')}):"
        )
        for ln in s.lines:
            unit_price = (ln.material_price or 0) + (ln.work_price or 0)
            summ = (ln.qty or 0) * unit_price
            lines.append(
                f"  строка #{ln.id}: {ln.name} | {ln.qty} {ln.unit} | "
                f"цена {unit_price} | сумма {summ}"
            )
    if not branch.sections:
        lines.append("(смета пустая)")
    return "\n".join(lines)


def _candidates(db: Session, queries: list[str]) -> tuple[str, list[CatalogItem]]:
    seen: dict[int, CatalogItem] = {}

    def _add(found: list[CatalogItem]) -> None:
        for it in found:
            if it.id not in seen:
                seen[it.id] = it

    for q in (queries or [])[:_MAX_QUERIES]:
        items, _ = catalog_service.search_items(
            db, q=q, limit=_PER_QUERY, in_characteristics=True
        )
        if not items and len(q.split()) > 1:
            # запрос слишком конкретный (характеристики/бренд в названии нет) —
            # переспрашиваем по отдельным значимым словам, чтобы найти категорию
            for word in q.split():
                if len(word) < 3:
                    continue
                _add(catalog_service.search_items(
                    db, q=word, limit=_PER_QUERY, in_characteristics=True)[0])
                if len(seen) >= _MAX_CANDIDATES:
                    break
        else:
            _add(items)
        if len(seen) >= _MAX_CANDIDATES:
            break
    items = list(seen.values())[:_MAX_CANDIDATES]
    if not items:
        return "(каталог: подходящих позиций не найдено)", items
    rows = []
    for it in items:
        work, material, _ = est_service.snapshot_line_values(db, it, None)
        price = work + material
        chars = ""
        if it.characteristics:
            pairs = ", ".join(f"{k}: {v}" for k, v in list(it.characteristics.items())[:6])
            chars = f" | {pairs}"
        rows.append(f"  {it.id} | {it.name} | {it.unit} | {it.kind} | цена {price}{chars}")
    text = (
        "КАНДИДАТЫ КАТАЛОГА (catalog_item_id | имя | ед | вид | цена | характеристики):\n"
        + "\n".join(rows)
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
        "до 5 КОРОТКИХ поисковых запросов по каталогу (1-2 слова: тип/категория позиции — "
        "например «камера», «видеокамера», «видеорегистратор», «кабель», «блок питания», "
        "«монтаж»). НЕ включай в запросы характеристики, бренды, модели и артикулы — "
        "только общее название типа, иначе поиск по названию ничего не найдёт. "
        "Если пользователь просит ДОБАВИТЬ, ПОДОБРАТЬ или ПОСОВЕТОВАТЬ оборудование/"
        "материалы — ОБЯЗАТЕЛЬНО верни запросы (НЕ пустой список). "
        "Пустой список — только если каталог не нужен (правка/вопрос по уже имеющимся "
        "строкам сметы).\n\n"
        f"СМЕТА:\n{context}"
    )
    step1 = ai_service.call_llm(
        db, "assistant",
        [{"role": "system", "content": search_prompt}, *convo],
        json_schema=schemas.SEARCH_SCHEMA, max_tokens=_MAX_TOKENS,
    )
    queries = step1.get("queries", []) if isinstance(step1, dict) else []

    cand_text, _ = _candidates(db, queries)

    # Шаг 2 — ответ + changeset
    ops_prompt = (
        "Ты — толковый помощник-сметчик внутри редактора смет. Отвечай по-русски, "
        "КОНКРЕТНО и КРАТКО, по существу ИМЕННО ЭТОЙ сметы — используй её реальные числа "
        "(суммы, кол-во, наценку, итоги из блока СМЕТА). НЕ задавай встречных вопросов, "
        "если можешь дать полезный ответ; не лей воду и не перечисляй, что «можно было бы» "
        "проверить — сразу делай это.\n"
        "Если просят ПРОВЕРИТЬ/проанализировать/посоветовать или задают вопрос — дай "
        "конкретные наблюдения и рекомендации по этой смете в reply (operations можно "
        "оставить пустым; либо предложи операции-исправления, если уместно). "
        "Если просят ИЗМЕНИТЬ смету — верни операции и кратко опиши их в reply.\n"
        "Операции (поле op): add_section{name}; "
        "add_catalog_line{section_name, catalog_item_id, qty}; "
        "add_custom_line{section_name, name, unit, qty, material_price, work_price}; "
        "set_qty{line_id, qty}; set_price{line_id, material_price?, work_price?}; "
        "delete_line{line_id}; delete_section{section_id}; "
        "set_section_markup{section_id, markup_percent}; set_vat{vat_enabled, vat_rate?}.\n"
        "ГЛАВНОЕ ПРАВИЛО: для оборудования и материалов ВСЕГДА бери позицию из списка "
        "КАНДИДАТЫ через add_catalog_line с её catalog_item_id — НЕ придумывай позиции и "
        "НЕ выдумывай цены (цена подставится из каталога автоматически). add_custom_line "
        "используй ТОЛЬКО когда в КАНДИДАТАХ нет ничего подходящего (например, монтаж/"
        "работа/услуга, которой нет в каталоге). Если в КАНДИДАТАХ пусто — скажи в reply, "
        "что в каталоге нет подходящих позиций, и предложи, что импортировать, "
        "а не выдумывай оборудование.\n"
        "Ссылайся ТОЛЬКО на реальные id из СМЕТЫ и КАНДИДАТОВ; раздел — по имени "
        "(section_name), можно создать add_section и в том же пакете добавлять в него строки.\n\n"
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

        # счётчик sort_order по разделам: collection sec.lines не обновляется до flush
        # при autoflush=False, поэтому len(sec.lines) дал бы одинаковый порядок всем
        # строкам пакета — ведём собственный счётчик, засеянный текущим числом строк.
        line_order: dict[int, int] = {}

        def _next_order(sec: em.EstimateSection) -> int:
            n = line_order.get(sec.id, len(sec.lines))
            line_order[sec.id] = n + 1
            return n

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
                    purchase_price_snapshot=purchase, sort_order=_next_order(sec),
                ))
            elif isinstance(op, schemas.AddCustomLine):
                sec = by_name.get(op.section_name)
                if sec is None:
                    raise ApplyError(f"Раздел «{op.section_name}» не найден")
                db.add(em.EstimateLine(
                    section_id=sec.id, name=op.name, unit=op.unit, qty=op.qty,
                    work_price=op.work_price, material_price=op.material_price,
                    sort_order=_next_order(sec),
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
