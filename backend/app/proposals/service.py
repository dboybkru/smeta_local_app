from sqlalchemy.orm import Session

from app.ai import service as ai_service
from app.estimates import models as est_models
from app.estimates import service as est_service
from app.profile import models as profile_models
from app.proposals.schemas import ProposalBlocks

PURPOSE = "proposal_generation"

PROPOSAL_SCHEMA = {
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
}


def build_prompt(
    estimate: est_models.Estimate, profile: profile_models.CompanyProfile | None
) -> str:
    lines: list[str] = []
    for branch in estimate.branches:
        for section in branch.sections:
            for ln in section.lines:
                lines.append(f"- {section.name}: {ln.name} ({ln.qty} {ln.unit})")
    totals = est_service.compute_totals(estimate)

    parts: list[str] = []
    if profile is not None:
        if profile.org_name:
            parts.append(f"Компания: {profile.org_name}")
        if profile.utp:
            parts.append("УТП: " + "; ".join(profile.utp))
        if profile.cases:
            parts.append("Кейсы: " + "; ".join(profile.cases))
        if profile.guarantee:
            parts.append(f"Гарантия: {profile.guarantee}")
    profile_block = "\n".join(parts) or "(профиль исполнителя не заполнен)"

    return (
        "Ты — копирайтер строительной компании. Составь продающее коммерческое "
        "предложение по смете. Блоки на русском, в тоне делового КП "
        "(заголовок-выгода, боль клиента, решение-результат, УТП, преимущества, "
        "условия, призыв к действию).\n\n"
        f"Объект: {estimate.object_name or '(не указан)'}\n"
        f"Итоговая стоимость: {totals['total']} руб.\n\n"
        "Состав работ:\n" + ("\n".join(lines) or "(позиции не добавлены)") + "\n\n"
        "Об исполнителе:\n" + profile_block
    )


def generate_proposal(
    db: Session,
    estimate: est_models.Estimate,
    profile: profile_models.CompanyProfile | None,
) -> dict:
    prompt = build_prompt(estimate, profile)
    blocks = ai_service.call_llm(
        db, PURPOSE, [{"role": "user", "content": prompt}], json_schema=PROPOSAL_SCHEMA
    )
    return ProposalBlocks.model_validate(blocks).model_dump()
