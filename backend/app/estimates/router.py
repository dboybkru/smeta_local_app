from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_active
from app.auth.models import User
from app.core.db import get_db
from app.estimates import models, schemas

router = APIRouter(prefix="/api", tags=["estimates"])


@router.get(
    "/clients",
    response_model=list[schemas.ClientOut],
    dependencies=[Depends(require_active)],
)
def list_clients(db: Session = Depends(get_db)):
    return db.scalars(select(models.Client).order_by(models.Client.name)).all()


@router.post("/clients", response_model=schemas.ClientOut, status_code=201)
def create_client(
    body: schemas.ClientIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_active),
):
    client = models.Client(name=body.name, default_price_level_id=body.default_price_level_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client
