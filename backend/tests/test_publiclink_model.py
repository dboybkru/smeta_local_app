from app.auth.models import User
from app.estimates.models import Estimate
from app.publiclinks.models import PublicLink


def test_public_link_defaults(db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Объект")
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
