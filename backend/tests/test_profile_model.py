import pytest
from sqlalchemy.exc import IntegrityError

from app.orgs.models import Organization
from app.profile.models import CompanyProfile


def _org(db_session, name="TestOrg"):
    o = Organization(name=name)
    db_session.add(o)
    db_session.commit()
    return o


def test_profile_defaults(db_session):
    o = _org(db_session)
    p = CompanyProfile(org_id=o.id, org_name="ООО Ромашка")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    assert p.org_name == "ООО Ромашка"
    assert p.contacts == {}
    assert p.utp == []
    assert p.cases == []
    assert p.inn == ""


def test_profile_unique_per_org(db_session):
    o = _org(db_session, "UniqueOrg")
    db_session.add(CompanyProfile(org_id=o.id))
    db_session.commit()
    db_session.add(CompanyProfile(org_id=o.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
