from sqlalchemy.orm import Session

from app.ai import crypto
from app.settings.models import AppSetting


def set_secret(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    enc = crypto.encrypt(value) if value else ""
    if row is None:
        db.add(AppSetting(key=key, value=enc))
    else:
        row.value = enc
    db.commit()


def get_secret(db: Session, key: str) -> str:
    row = db.get(AppSetting, key)
    if row is None or not row.value:
        return ""
    return crypto.decrypt(row.value)


def has_secret(db: Session, key: str) -> bool:
    row = db.get(AppSetting, key)
    return bool(row and row.value)
