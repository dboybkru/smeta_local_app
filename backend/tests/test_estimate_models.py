from decimal import Decimal

from app.auth.models import User
from app.estimates.models import (
    Client,
    Estimate,
    EstimateBranch,
    EstimateLine,
    EstimateSection,
)


def _owner(db):
    u = User(email="o@x.ru", name="O", role="estimator", status="active")
    db.add(u)
    db.commit()
    return u


def test_estimate_defaults_and_relationships(db_session):
    owner = _owner(db_session)
    est = Estimate(owner_id=owner.id, object_name="Объект 1")
    db_session.add(est)
    db_session.commit()
    assert est.status == "draft"
    assert est.vat_enabled is False
    assert est.vat_rate == Decimal("20")
    assert est.created_at is not None


def test_cascade_delete_estimate_removes_children(db_session):
    owner = _owner(db_session)
    est = Estimate(owner_id=owner.id, object_name="O")
    branch = EstimateBranch(estimate=est, name="Базовая")
    section = EstimateSection(branch=branch, name="Раздел 1")
    line = EstimateLine(section=section, name="Позиция", unit="шт", qty=Decimal("2"))
    db_session.add(est)
    db_session.commit()
    assert db_session.query(EstimateLine).count() == 1

    db_session.delete(est)
    db_session.commit()
    assert db_session.query(EstimateBranch).count() == 0
    assert db_session.query(EstimateSection).count() == 0
    assert db_session.query(EstimateLine).count() == 0
