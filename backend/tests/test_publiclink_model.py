from sqlalchemy import select

from app.auth.models import User
from app.estimates.models import Estimate
from app.orgs.models import Organization
from app.publiclinks.models import PublicLink


def test_public_link_defaults(db_session):
    org = db_session.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db_session.add(org)
        db_session.commit()
    u = User(email="u@x.ru", name="U", role="estimator", status="active", org_id=org.id)
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, org_id=org.id, object_name="Объект")
    db_session.add(est)
    db_session.commit()
    link = PublicLink(estimate_id=est.id, token="abc123")
    db_session.add(link)
    db_session.commit()
    db_session.refresh(link)
    assert link.level == "full"
    assert link.revoked is False
    assert link.watermark_enabled is False
    assert link.expires_at is None
