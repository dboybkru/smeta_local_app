import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client
from app.ai.errors import AIError, AINotConfigured
from app.ai.models import AIModel, AIProvider, AIPurpose, AIUsage


def record_usage(
    db: Session, provider: AIProvider, model: AIModel, purpose: str, result: dict
) -> None:
    """Записать фактический расход AI-вызова в журнал ai_usage."""
    db.add(AIUsage(
        provider_name=provider.name,
        model_id=model.model_id,
        purpose=purpose,
        prompt_tokens=result.get("prompt_tokens", 0),
        completion_tokens=result.get("completion_tokens", 0),
        cost_rub=result.get("cost_rub"),
    ))
    db.commit()


def _resolve(db: Session, model_id: int | None) -> tuple[AIProvider, AIModel] | None:
    """Модель по id → (провайдер, модель), если всё включено и есть ключ."""
    if model_id is None:
        return None
    model = db.get(AIModel, model_id)
    if model is None or not model.enabled:
        return None
    provider = db.get(AIProvider, model.provider_id)
    if provider is None or not provider.enabled or not provider.api_key_encrypted:
        return None
    return provider, model


def call_llm(
    db: Session,
    purpose_key: str,
    messages: list[dict],
    *,
    json_schema: dict | None = None,
    max_tokens: int = 2000,
) -> dict | str:
    """Резолв цель→модель→провайдер, вызов с фолбэком. dict если json_schema, иначе str."""
    purpose = db.scalars(
        select(AIPurpose).where(AIPurpose.key == purpose_key)
    ).first()
    if purpose is None or not purpose.enabled:
        raise AINotConfigured(f"Цель '{purpose_key}' не настроена")

    primary = _resolve(db, purpose.primary_model_id)
    if primary is None:
        raise AINotConfigured(f"Для цели '{purpose_key}' не выбрана рабочая модель")
    fallback = _resolve(db, purpose.fallback_model_id)

    json_mode = json_schema is not None
    sent = list(messages)
    if json_mode:
        schema_text = json.dumps(json_schema, ensure_ascii=False)
        sent = [
            {"role": "system",
             "content": "Верни ТОЛЬКО валидный JSON по схеме: " + schema_text},
            *messages,
        ]

    candidates = [primary] + ([fallback] if fallback else [])
    last_err: Exception | None = None
    for provider, model in candidates:
        try:
            result = client.chat_completion(
                provider, model.model_id, sent, max_tokens=max_tokens, json_mode=json_mode
            )
            record_usage(db, provider, model, purpose_key, result)
            content = result["content"]
            return json.loads(content) if json_mode else content
        except (AIError, json.JSONDecodeError) as exc:
            last_err = exc
            continue
    raise AIError(f"Все модели цели '{purpose_key}' недоступны: {last_err}")
