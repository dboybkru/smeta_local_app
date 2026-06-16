from datetime import UTC, datetime, timedelta

from app.auth.models import User
from app.orgs.models import Organization


def test_user_has_invite_token_columns(db_session):
    o = Organization(name="IT"); db_session.add(o); db_session.commit()
    u = User(email="i@x.ru", name="", role="estimator", status="invited", org_id=o.id,
             invite_token="tok123", invite_expires_at=datetime.now(UTC) + timedelta(days=7))
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    assert u.invite_token == "tok123" and u.invite_expires_at is not None
