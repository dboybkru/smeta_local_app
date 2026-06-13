from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import service as est_service
from app.publiclinks import models, schemas, service

router = APIRouter(prefix="/api", tags=["public-links"])


@router.post(
    "/estimates/{estimate_id}/public-links",
    response_model=schemas.PublicLinkOut,
    status_code=201,
)
def create_public_link(
    estimate_id: int,
    body: schemas.PublicLinkIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    est_service.require_write(est, user)
    return service.create_link(db, est.id, body)


@router.get(
    "/estimates/{estimate_id}/public-links",
    response_model=list[schemas.PublicLinkOut],
)
def list_public_links(
    estimate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    est = est_service.get_owned_estimate(db, estimate_id, user)
    return service.list_links(db, est.id)


@router.delete("/public-links/{link_id}", status_code=204)
def delete_public_link(
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    link = db.get(models.PublicLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    est = est_service.get_owned_estimate(db, link.estimate_id, user)
    est_service.require_write(est, user)
    service.revoke_link(db, link)
