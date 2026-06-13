import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.profile.models import CompanyProfile


def _user(db_session, email="u@x.ru"):
    u = User(email=email, name="U", role="estimator", status="active")
    db_session.add(u)
    db_session.commit()
    return u


def test_profile_defaults(db_session):
    u = _user(db_session)
    p = CompanyProfile(user_id=u.id, org_name="ООО Ромашка")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    assert p.org_name == "ООО Ромашка"
    assert p.contacts == {}
    assert p.utp == []
    assert p.cases == []
    assert p.inn == ""


def test_profile_unique_per_user(db_session):
    u = _user(db_session)
    db_session.add(CompanyProfile(user_id=u.id))
    db_session.commit()
    db_session.add(CompanyProfile(user_id=u.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
