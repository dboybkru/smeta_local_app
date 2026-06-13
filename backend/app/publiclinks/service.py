import secrets
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.publiclinks import models, schemas


def create_link(db: Session, estimate_id: int, body: schemas.PublicLinkIn) -> models.PublicLink:
    link = models.PublicLink(
        estimate_id=estimate_id,
        token=secrets.token_urlsafe(24),
        level=body.level,
        expires_at=body.expires_at,
        watermark_enabled=body.watermark_enabled,
        watermark_text=body.watermark_text,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def list_links(db: Session, estimate_id: int) -> list[models.PublicLink]:
    return db.scalars(
        select(models.PublicLink)
        .where(models.PublicLink.estimate_id == estimate_id)
        .order_by(models.PublicLink.created_at.desc())
    ).all()


def revoke_link(db: Session, link: models.PublicLink) -> None:
    link.revoked = True
    db.commit()


def _expired(link: models.PublicLink) -> bool:
    if link.expires_at is None:
        return False
    exp = link.expires_at
    if exp.tzinfo is None:  # SQLite хранит naive — считаем UTC
        exp = exp.replace(tzinfo=UTC)
    return exp < datetime.now(UTC)


def resolve_token(db: Session, token: str) -> models.PublicLink:
    """Публичный доступ: не найден/отозван → 404; просрочен → 410."""
    link = db.scalars(
        select(models.PublicLink).where(models.PublicLink.token == token)
    ).first()
    if link is None or link.revoked:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    if _expired(link):
        raise HTTPException(status_code=410, detail="Срок действия ссылки истёк")
    return link
