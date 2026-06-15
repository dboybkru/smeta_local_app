import pytest
from fastapi import HTTPException

from app.auth.deps import current_org, require_org_admin, require_superuser
from app.auth.models import User


def test_current_org_returns_user_org():
    u = User(id=1, org_id=7, role="estimator", status="active")
    assert current_org(u) == 7


def test_current_org_none_raises_403():
    u = User(id=1, org_id=None, role="estimator", status="active")
    with pytest.raises(HTTPException) as e:
        current_org(u)
    assert e.value.status_code == 403


def test_require_org_admin_allows_admin_and_superuser():
    assert require_org_admin(User(id=1, org_id=1, role="org_admin", status="active"))
    assert require_org_admin(User(id=2, org_id=1, role="estimator", status="active", is_superuser=True))


def test_require_org_admin_denies_estimator():
    with pytest.raises(HTTPException) as e:
        require_org_admin(User(id=3, org_id=1, role="estimator", status="active"))
    assert e.value.status_code == 403
