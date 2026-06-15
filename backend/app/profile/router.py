from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import current_org, require_org_admin
from app.auth.models import User
from app.core.db import get_db
from app.profile import schemas, service

router = APIRouter(prefix="/api", tags=["profile"])

# Пустой профиль для организации без сохранённых реквизитов (GET до первого PUT).
_EMPTY = schemas.ProfileOut(
    id=0, org_name="", inn="", contacts={}, bank_requisites="",
    utp=[], cases=[], guarantee="", logo_url="",
    updated_at=datetime(1970, 1, 1, tzinfo=UTC),
)


@router.get("/profile", response_model=schemas.ProfileOut)
def get_profile(db: Session = Depends(get_db), org_id: int = Depends(current_org)):
    profile = service.get_profile(db, org_id)
    if profile is None:
        return _EMPTY
    return profile


@router.put("/profile", response_model=schemas.ProfileOut)
def put_profile(
    body: schemas.ProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_org_admin),
    org_id: int = Depends(current_org),
):
    return service.upsert_profile(db, org_id, body)
