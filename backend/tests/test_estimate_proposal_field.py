from sqlalchemy import select

from app.auth.models import User
from app.estimates.models import Estimate
from app.orgs.models import Organization


def _get_org(db_session):
    org = db_session.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db_session.add(org)
        db_session.commit()
    return org


def _user(db_session):
    org = _get_org(db_session)
    u = User(email="u@x.ru", name="U", role="estimator", status="active", org_id=org.id)
    db_session.add(u)
    db_session.commit()
    return u


def test_proposal_defaults_none_and_stores_dict(db_session):
    u = _user(db_session)
    org = _get_org(db_session)
    est = Estimate(owner_id=u.id, org_id=org.id, object_name="Объект")
    db_session.add(est)
    db_session.commit()
    db_session.refresh(est)
    assert est.proposal is None

    est.proposal = {"title": "Ремонт под ключ", "advantages": ["быстро", "качественно"]}
    db_session.commit()
    db_session.refresh(est)
    assert est.proposal["title"] == "Ремонт под ключ"
    assert est.proposal["advantages"] == ["быстро", "качественно"]
