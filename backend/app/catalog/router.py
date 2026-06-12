from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_active, require_admin
from app.catalog.models import ItemPrice, PriceLevel
from app.catalog.schemas import PriceLevelIn, PriceLevelOut, PriceLevelPatch
from app.core.db import get_db

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get(
    "/price-levels", response_model=list[PriceLevelOut], dependencies=[Depends(require_active)]
)
def list_price_levels(db: Session = Depends(get_db)):
    return db.scalars(select(PriceLevel).order_by(PriceLevel.sort_order, PriceLevel.id)).all()


@router.post(
    "/price-levels",
    response_model=PriceLevelOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_price_level(body: PriceLevelIn, db: Session = Depends(get_db)):
    if db.scalar(select(PriceLevel).where(PriceLevel.name == body.name)):
        raise HTTPException(status_code=409, detail="Уровень с таким именем уже есть")
    level = PriceLevel(name=body.name, sort_order=body.sort_order)
    db.add(level)
    db.commit()
    db.refresh(level)
    return level


@router.patch(
    "/price-levels/{level_id}",
    response_model=PriceLevelOut,
    dependencies=[Depends(require_admin)],
)
def update_price_level(level_id: int, body: PriceLevelPatch, db: Session = Depends(get_db)):
    level = db.get(PriceLevel, level_id)
    if level is None:
        raise HTTPException(status_code=404, detail="Уровень не найден")
    if body.name is not None and body.name != level.name:
        if db.scalar(select(PriceLevel).where(PriceLevel.name == body.name)):
            raise HTTPException(status_code=409, detail="Уровень с таким именем уже есть")
        level.name = body.name
    if body.sort_order is not None:
        level.sort_order = body.sort_order
    db.commit()
    db.refresh(level)
    return level


@router.delete(
    "/price-levels/{level_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def delete_price_level(level_id: int, db: Session = Depends(get_db)):
    level = db.get(PriceLevel, level_id)
    if level is None:
        raise HTTPException(status_code=404, detail="Уровень не найден")
    if db.scalar(select(ItemPrice).where(ItemPrice.price_level_id == level_id).limit(1)):
        raise HTTPException(
            status_code=409, detail="Уровень используется в ценах — удалить нельзя"
        )
    db.delete(level)
    db.commit()
