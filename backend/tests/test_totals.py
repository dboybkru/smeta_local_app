from decimal import Decimal

from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.estimates.service import compute_totals


def _estimate(vat_enabled=False, vat_rate="20", markup="0", lines=()):
    est = Estimate(owner_id=1, object_name="O", vat_enabled=vat_enabled, vat_rate=Decimal(vat_rate))
    branch = EstimateBranch(estimate=est, name="Базовая")
    section = EstimateSection(branch=branch, name="S", markup_percent=Decimal(markup))
    for wp, mp, qty, purch in lines:
        section.lines.append(EstimateLine(
            name="L", unit="шт", qty=Decimal(qty),
            work_price=Decimal(wp), material_price=Decimal(mp),
            purchase_price_snapshot=Decimal(purch) if purch is not None else None,
        ))
    return est


def test_line_and_section_sums_no_markup_no_vat():
    est = _estimate(lines=[("0", "150", "2", None), ("500", "0", "1", None)])
    t = compute_totals(est)
    sect = t["sections"][0]
    assert sect["materials"] == Decimal("300.00")
    assert sect["works"] == Decimal("500.00")
    assert sect["total"] == Decimal("800.00")
    assert t["subtotal"] == Decimal("800.00")
    assert t["vat"] == Decimal("0.00")
    assert t["total"] == Decimal("800.00")


def test_markup_applies_to_section_sell_sum():
    est = _estimate(markup="10", lines=[("0", "100", "1", None)])
    t = compute_totals(est)
    assert t["sections"][0]["total"] == Decimal("110.00")
    assert t["subtotal"] == Decimal("110.00")


def test_vat_added_on_top():
    est = _estimate(vat_enabled=True, vat_rate="20", lines=[("0", "100", "1", None)])
    t = compute_totals(est)
    assert t["subtotal"] == Decimal("100.00")
    assert t["vat"] == Decimal("20.00")
    assert t["total"] == Decimal("120.00")


def test_margin_is_sell_minus_purchase_at_section_level():
    # material sell 150 x2 = 300, markup 10% -> 330 sell; purchase 100 x2 = 200; margin 130
    est = _estimate(markup="10", lines=[("0", "150", "2", "100")])
    t = compute_totals(est)
    assert t["sections"][0]["purchase"] == Decimal("200.00")
    assert t["sections"][0]["margin"] == Decimal("130.00")
    assert t["margin"] == Decimal("130.00")


def test_missing_purchase_counts_as_zero_purchase():
    est = _estimate(lines=[("0", "100", "1", None)])
    t = compute_totals(est)
    assert t["sections"][0]["purchase"] == Decimal("0.00")
    assert t["sections"][0]["margin"] == Decimal("100.00")
