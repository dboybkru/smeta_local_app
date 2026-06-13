import json

from app.core.config import settings
from app.estimates import models as est_models
from app.estimates import service as est_service
from app.profile import models as profile_models
from app.proposals.schemas import ProposalBlocks

MODEL = "claude-opus-4-8"


class ProposalAINotConfigured(Exception):
    """ANTHROPIC_API_KEY не задан — AI-генерация недоступна."""


class ProposalAIError(Exception):
    """Ошибка вызова Claude (сеть/таймаут/невалидный ответ)."""


def build_prompt(
    estimate: est_models.Estimate, profile: profile_models.CompanyProfile | None
) -> str:
    """Промпт из сметы (объект, позиции, итог) и профиля исполнителя."""
    lines: list[str] = []
    for branch in estimate.branches:
        for section in branch.sections:
            for ln in section.lines:
                lines.append(f"- {section.name}: {ln.name} ({ln.qty} {ln.unit})")
    totals = est_service.compute_totals(estimate)

    profile_parts: list[str] = []
    if profile is not None:
        if profile.org_name:
            profile_parts.append(f"Компания: {profile.org_name}")
        if profile.utp:
            profile_parts.append("УТП: " + "; ".join(profile.utp))
        if profile.cases:
            profile_parts.append("Кейсы: " + "; ".join(profile.cases))
        if profile.guarantee:
            profile_parts.append(f"Гарантия: {profile.guarantee}")
    profile_block = "\n".join(profile_parts) or "(профиль исполнителя не заполнен)"

    return (
        "Ты — копирайтер строительной компании. Составь продающее коммерческое "
        "предложение по смете. Верни блоки на русском языке в тоне делового КП "
        "(заголовок-выгода, боль клиента, решение-результат, УТП, преимущества, "
        "условия, призыв к действию).\n\n"
        f"Объект: {estimate.object_name or '(не указан)'}\n"
        f"Итоговая стоимость: {totals['total']} руб.\n\n"
        "Состав работ:\n" + ("\n".join(lines) or "(позиции не добавлены)") + "\n\n"
        "Об исполнителе:\n" + profile_block
    )


def _call_claude(prompt: str) -> dict:
    """Единственный seam к Claude API. В тестах замокан monkeypatch'ем."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            output_config={"format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
            timeout=60.0,
        )
    except anthropic.APIError as exc:  # сеть/таймаут/перегрузка
        raise ProposalAIError(str(exc)) from exc
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProposalAIError("Claude вернул невалидный JSON") from exc


_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "pain": {"type": "string"},
        "solution": {"type": "string"},
        "advantages": {"type": "array", "items": {"type": "string"}},
        "terms": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["title", "subtitle", "pain", "solution", "advantages", "terms", "cta"],
    "additionalProperties": False,
}


def generate_proposal(
    estimate: est_models.Estimate, profile: profile_models.CompanyProfile | None
) -> dict:
    if not settings.anthropic_api_key:
        raise ProposalAINotConfigured("AI не настроен")
    prompt = build_prompt(estimate, profile)
    blocks = _call_claude(prompt)
    return ProposalBlocks.model_validate(blocks).model_dump()
