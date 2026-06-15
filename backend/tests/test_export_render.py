import pytest

from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.export import context as ctx
from app.export import render


def _estimate(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Дом 120 м²")
    est.proposal = {"title": "Ремонт под ключ", "cta": "Звоните"}
    branch = EstimateBranch(name="Базовая")
    section = EstimateSection(name="Полы", markup_percent=0)
    section.lines.append(
        EstimateLine(name="Стяжка", unit="м²", qty=50, work_price=400,
                     material_price=200, purchase_price_snapshot=150)
    )
    branch.sections.append(section)
    est.branches.append(branch)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


def test_render_html_full_includes_proposal_and_lines(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=False)
    html = render.render_html(context)
    assert "Ремонт под ключ" in html
    assert "Стяжка" in html
    assert "Дом 120 м²" in html


def test_public_html_has_no_margin_or_purchase(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=True)
    html = render.render_html(context)
    assert "Маржа" not in html
    assert "Закупка" not in html
    assert "150" not in html  # закупочная цена не утекла


def test_watermark_present_when_enabled(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=True)
    html = render.render_html(context, watermark="ОБРАЗЕЦ")
    assert "ОБРАЗЕЦ" in html


def test_html_to_pdf_signature(db_session):
    try:
        weasyprint = pytest.importorskip("weasyprint")  # noqa: F841
    except OSError:
        pytest.skip("системные библиотеки weasyprint недоступны")
    try:
        pdf = render.html_to_pdf("<html><body><h1>Тест</h1></body></html>")
    except OSError:
        pytest.skip("системные библиотеки weasyprint недоступны")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000
