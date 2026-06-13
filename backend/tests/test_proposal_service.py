import pytest

from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.profile.models import CompanyProfile
from app.proposals import service


def _estimate_with_lines(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Квартира 80 м²")
    branch = EstimateBranch(name="Базовая")
    section = EstimateSection(name="Демонтаж")
    section.lines.append(
        EstimateLine(name="Демонтаж перегородок", unit="м²", qty=20, work_price=500, material_price=0)
    )
    branch.sections.append(section)
    est.branches.append(branch)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    profile = CompanyProfile(
        user_id=u.id, org_name="ООО Ромашка", utp=["Гарантия 5 лет"], guarantee="5 лет"
    )
    db_session.add(profile)
    db_session.commit()
    return est, profile


def test_build_prompt_includes_object_lines_and_profile(db_session):
    est, profile = _estimate_with_lines(db_session)
    prompt = service.build_prompt(est, profile)
    assert "Квартира 80 м²" in prompt
    assert "Демонтаж перегородок" in prompt
    assert "ООО Ромашка" in prompt
    assert "Гарантия 5 лет" in prompt


def test_generate_proposal_writes_blocks(db_session, monkeypatch):
    est, profile = _estimate_with_lines(db_session)
    monkeypatch.setattr(service.settings, "anthropic_api_key", "sk-test")
    fake = {
        "title": "Ремонт под ключ", "subtitle": "Качество и сроки",
        "pain": "Долго и дорого", "solution": "Сделаем за 30 дней",
        "advantages": ["Свои бригады"], "terms": "Аванс 30%", "cta": "Свяжитесь с нами",
    }
    monkeypatch.setattr(service, "_call_claude", lambda prompt: fake)
    result = service.generate_proposal(est, profile)
    assert result["title"] == "Ремонт под ключ"
    assert result["advantages"] == ["Свои бригады"]
    # generate_proposal прогоняет ответ через ProposalBlocks — ровно 7 нормализованных блоков
    assert set(result.keys()) == {
        "title", "subtitle", "pain", "solution", "advantages", "terms", "cta"
    }


def test_generate_proposal_raises_when_no_key(db_session, monkeypatch):
    est, profile = _estimate_with_lines(db_session)
    monkeypatch.setattr(service.settings, "anthropic_api_key", "")
    with pytest.raises(service.ProposalAINotConfigured):
        service.generate_proposal(est, profile)
