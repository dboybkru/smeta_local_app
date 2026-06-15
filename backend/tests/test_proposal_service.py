import pytest

from sqlalchemy import select

from app.ai import service as ai_service
from app.ai.errors import AINotConfigured
from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.orgs.models import Organization
from app.profile.models import CompanyProfile
from app.proposals import service


def _get_org(db_session):
    org = db_session.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db_session.add(org)
        db_session.commit()
    return org


def _estimate_with_lines(db_session):
    org = _get_org(db_session)
    u = User(email="u@x.ru", name="U", role="estimator", status="active", org_id=org.id)
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, org_id=org.id, object_name="Квартира 80 м²")
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
    profile = CompanyProfile(user_id=u.id, org_name="ООО Ромашка",
                             utp=["Гарантия 5 лет"], guarantee="5 лет")
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
    fake = {"title": "Ремонт под ключ", "subtitle": "Качество",
            "pain": "Долго", "solution": "За 30 дней",
            "advantages": ["Свои бригады"], "terms": "Аванс 30%", "cta": "Звоните"}
    monkeypatch.setattr(ai_service, "call_llm", lambda db, key, messages, **kw: fake)
    result = service.generate_proposal(db_session, est, profile)
    assert result["title"] == "Ремонт под ключ"
    assert result["advantages"] == ["Свои бригады"]
    assert set(result.keys()) == {
        "title", "subtitle", "pain", "solution", "advantages", "terms", "cta"
    }


def test_generate_proposal_uses_proposal_generation_purpose(db_session, monkeypatch):
    est, profile = _estimate_with_lines(db_session)
    seen = {}

    def fake(db, key, messages, **kw):
        seen["key"] = key
        seen["json_schema"] = kw.get("json_schema")
        return {"title": "T", "subtitle": "", "pain": "", "solution": "",
                "advantages": [], "terms": "", "cta": ""}

    monkeypatch.setattr(ai_service, "call_llm", fake)
    service.generate_proposal(db_session, est, profile)
    assert seen["key"] == "proposal_generation"
    assert seen["json_schema"] is not None


def test_generate_proposal_propagates_not_configured(db_session, monkeypatch):
    est, profile = _estimate_with_lines(db_session)
    def boom(*a, **k):
        raise AINotConfigured("нет модели")
    monkeypatch.setattr(ai_service, "call_llm", boom)
    with pytest.raises(AINotConfigured):
        service.generate_proposal(db_session, est, profile)
