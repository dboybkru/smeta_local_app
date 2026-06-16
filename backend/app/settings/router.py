from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_superuser
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


@router.get("/dadata", dependencies=[Depends(require_superuser)])
def get_dadata(db: Session = Depends(get_db)):
    return _status(db)


@router.put("/dadata")
def set_dadata(
    body: DadataIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_superuser),
):
    if body.token.strip():
        service.set_secret(db, DADATA_KEY, body.token.strip())
    if body.secret.strip():
        service.set_secret(db, DADATA_SECRET, body.secret.strip())
    return _status(db)


@router.get("/yandex", dependencies=[Depends(require_superuser)])
def get_yandex(db: Session = Depends(get_db)):
    return _yandex_status(db)


@router.put("/yandex")
def set_yandex(
    body: YandexOAuthIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_superuser),
):
    if body.client_id.strip():
        service.set_secret(db, YANDEX_CLIENT_ID, body.client_id.strip())
    if body.secret.strip():
        service.set_secret(db, YANDEX_CLIENT_SECRET, body.secret.strip())
    return _yandex_status(db)


SMTP_KEYS = {
    "host": "smtp_host",
    "port": "smtp_port",
    "user": "smtp_user",
    "from_addr": "smtp_from",
    "tls": "smtp_tls",
}
SMTP_PASSWORD = "smtp_password"


class SmtpIn(BaseModel):
    host: str = ""
    port: str = ""
    user: str = ""
    password: str = ""
    from_addr: str = ""
    tls: str = ""


def _smtp_status(db: Session) -> dict:
    out = {field: service.get_secret(db, key) for field, key in SMTP_KEYS.items()}
    out["has_password"] = service.has_secret(db, SMTP_PASSWORD)
    return out


@router.get("/smtp", dependencies=[Depends(require_superuser)])
def get_smtp(db: Session = Depends(get_db)):
    return _smtp_status(db)


@router.put("/smtp")
def set_smtp(
    body: SmtpIn,
    db: Session = Depends(get_db),
    _: object = Depends(require_superuser),
):
    for field, key in SMTP_KEYS.items():
        val = getattr(body, field).strip()
        if val:
            service.set_secret(db, key, val)
    if body.password.strip():
        service.set_secret(db, SMTP_PASSWORD, body.password.strip())
    return _smtp_status(db)
