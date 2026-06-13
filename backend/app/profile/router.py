from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.profile import schemas, service

router = APIRouter(prefix="/api", tags=["profile"])

# Пустой профиль для пользователя без сохранённых реквизитов (GET до первого PUT).
_EMPTY = schemas.ProfileOut(
    id=0, org_name="", inn="", contacts={}, bank_requisites="",
    utp=[], cases=[], guarantee="", logo_url="",
    updated_at=datetime(1970, 1, 1, tzinfo=UTC),
)


@router.get("/profile", response_model=schemas.ProfileOut)
def get_profile(db: Session = Depends(get_db), user: User = Depends(require_active)):
    profile = service.get_profile(db, user.id)
    if profile is None:
        return _EMPTY
    return profile


@router.put("/profile", response_model=schemas.ProfileOut)
def put_profile(
    body: schemas.ProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    return service.upsert_profile(db, user.id, body)
