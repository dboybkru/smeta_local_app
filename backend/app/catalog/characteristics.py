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
