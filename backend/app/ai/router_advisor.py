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
