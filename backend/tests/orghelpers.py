"""Shared test helpers for single-org setup.

Provides get_or_create_org(db) — returns the first Organization in the test DB
(creates one named "TestOrg" if the table is empty). Import and alias to the
local name each test file used before this module existed, so call-sites stay
unchanged:

    from tests.orghelpers import get_or_create_org as _get_org
    # or
    from tests.orghelpers import get_or_create_org as _get_or_create_org

Do NOT use this helper for multi-org isolation tests (test_estimate_isolation,
test_catalog_isolation, etc.) that create named distinct orgs on purpose.
"""

from sqlalchemy import select

from app.orgs.models import Organization


def get_or_create_org(db):
    """Return the first Organization, creating it if the table is empty."""
    org = db.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db.add(org)
        db.commit()
    return org
