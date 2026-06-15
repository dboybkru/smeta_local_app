from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.orgs.models import Organization


def list_orgs(db: Session) -> list[dict]:
    rows = db.execute(
        select(Organization, func.count(User.id))
        .outerjoin(User, User.org_id == Organization.id)
        .group_by(Organization.id)
        .order_by(Organization.name)
    ).all()
    return [{"id": o.id, "name": o.name, "user_count": n} for o, n in rows]


def create_org(db: Session, name: str) -> Organization:
    org = Organization(name=name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def get_org(db: Session, org_id: int) -> Organization | None:
    return db.get(Organization, org_id)
