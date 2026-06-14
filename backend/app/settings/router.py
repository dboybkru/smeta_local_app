from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.auth.models import User
from app.core.db import get_db
from app.settings import service

router = APIRouter(prefix="/api/settings", tags=["settings"])

DADATA_KEY = "dadata_token"
DADATA_SECRET = "dadata_secret"


class DadataIn(BaseModel):
    token: str = ""
    secret: str = ""


def _status(db: Session) -> dict:
    return {
        "has_token": service.has_secret(db, DADATA_KEY),
        "has_secret": service.has_secret(db, DADATA_SECRET),
    }


@router.get("/dadata", dependencies=[Depends(require_admin)])
def get_dadata(db: Session = Depends(get_db)):
    return _status(db)


@router.put("/dadata", dependencies=[Depends(require_admin)])
def set_dadata(body: DadataIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if body.token.strip():
        service.set_secret(db, DADATA_KEY, body.token.strip())
    if body.secret.strip():
        service.set_secret(db, DADATA_SECRET, body.secret.strip())
    return _status(db)
