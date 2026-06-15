from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_superuser as require_admin
from app.auth.models import User
from app.core.db import get_db
from app.settings import service

router = APIRouter(prefix="/api/settings", tags=["settings"])

DADATA_KEY = "dadata_token"
DADATA_SECRET = "dadata_secret"

YANDEX_CLIENT_ID = "yandex_client_id"
YANDEX_CLIENT_SECRET = "yandex_client_secret"


class DadataIn(BaseModel):
    token: str = ""
    secret: str = ""


class YandexOAuthIn(BaseModel):
    client_id: str = ""
    secret: str = ""


def _status(db: Session) -> dict:
    return {
        "has_token": service.has_secret(db, DADATA_KEY),
        "has_secret": service.has_secret(db, DADATA_SECRET),
    }


def _yandex_status(db: Session) -> dict:
    return {
        "client_id": service.get_secret(db, YANDEX_CLIENT_ID),
        "has_secret": service.has_secret(db, YANDEX_CLIENT_SECRET),
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


@router.get("/yandex", dependencies=[Depends(require_admin)])
def get_yandex(db: Session = Depends(get_db)):
    return _yandex_status(db)


@router.put("/yandex", dependencies=[Depends(require_admin)])
def set_yandex(
    body: YandexOAuthIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if body.client_id.strip():
        service.set_secret(db, YANDEX_CLIENT_ID, body.client_id.strip())
    if body.secret.strip():
        service.set_secret(db, YANDEX_CLIENT_SECRET, body.secret.strip())
    return _yandex_status(db)
