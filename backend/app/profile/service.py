from sqlalchemy import select
from sqlalchemy.orm import Session

from app.profile import models, schemas


def get_profile(db: Session, org_id: int) -> models.CompanyProfile | None:
    return db.scalars(
        select(models.CompanyProfile).where(models.CompanyProfile.org_id == org_id)
    ).first()


def upsert_profile(
    db: Session, org_id: int, body: schemas.ProfileIn
) -> models.CompanyProfile:
    profile = get_profile(db, org_id)
    if profile is None:
        profile = models.CompanyProfile(org_id=org_id)
        db.add(profile)
    profile.org_name = body.org_name
    profile.inn = body.inn
    profile.contacts = body.contacts.model_dump()
    profile.bank_requisites = body.bank_requisites
    profile.utp = body.utp
    profile.cases = body.cases
    profile.guarantee = body.guarantee
    profile.logo_url = body.logo_url
    db.commit()
    db.refresh(profile)
    return profile
