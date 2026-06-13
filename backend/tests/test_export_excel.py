import io

from openpyxl import load_workbook

from app.auth.models import User
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.export import context as ctx
from app.export.excel import render_xlsx


def _estimate(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Квартира")
    branch = EstimateBranch(name="Базовая")
    section = EstimateSection(name="Стены", markup_percent=10)
    section.lines.append(
        EstimateLine(name="Штукатурка", unit="м²", qty=10, work_price=300,
                     material_price=100, purchase_price_snapshot=80)
    )
    branch.sections.append(section)
    est.branches.append(branch)
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    return est


def test_public_context_strips_margin_and_purchase(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=True)
    assert context["totals"]["margin"] is None
    assert context["totals"]["purchase"] is None
    for section in context["sections"]:
        assert section["totals"]["margin"] is None
        for line in section["lines"]:
            assert "purchase_price_snapshot" not in line


def test_private_context_keeps_margin(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="full", public=False)
    assert context["totals"]["margin"] is not None


def test_render_xlsx_is_valid_workbook(db_session):
    est = _estimate(db_session)
    context = ctx.build_export_context(est, level="estimate", public=False)
    data = render_xlsx(context)
    assert isinstance(data, bytes) and len(data) > 0
    wb = load_workbook(io.BytesIO(data))
    ws = wb.active
    text = "\n".join(
        str(c.value) for row in ws.iter_rows() for c in row if c.value is not None
    )
    assert "Квартира" in text
    assert "Штукатурка" in text
    assert "Стены" in text
