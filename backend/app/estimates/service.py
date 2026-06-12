from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.catalog.models import CatalogItem, PriceLevel
from app.catalog.service import latest_prices_for
from app.estimates import models


def visible_estimates(db: Session, user: User):
    """Estimator видит свои; admin/viewer — все."""
    query = select(models.Estimate).order_by(models.Estimate.created_at.desc())
    if user.role == "estimator":
        query = query.where(models.Estimate.owner_id == user.id)
    return db.scalars(query).all()


def get_owned_estimate(db: Session, estimate_id: int, user: User) -> models.Estimate:
    """Смета, которую пользователь может ЧИТАТЬ, иначе 404. Estimator — только свои."""
    est = db.get(models.Estimate, estimate_id)
    if est is None:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    return est


def require_write(est: models.Estimate, user: User) -> None:
    """Estimator пишет только свои; admin — любые; viewer — нельзя."""
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Просмотр без права изменения")
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Смета не найдена")


def get_owned_section(db: Session, section_id: int, user: User) -> models.EstimateSection:
    section = db.get(models.EstimateSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    est = section.branch.estimate
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    return section


def get_owned_line(db: Session, line_id: int, user: User) -> models.EstimateLine:
    line = db.get(models.EstimateLine, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    est = line.section.branch.estimate
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    return line


def base_branch(est: models.Estimate) -> models.EstimateBranch:
    """Единственная базовая ветка (варианты отложены)."""
    return est.branches[0]


ZAKUPKA_LEVEL_NAME = "Закупка"


def snapshot_line_values(
    db: Session,
    item: CatalogItem,
    client: models.Client | None,
) -> tuple[Decimal, Decimal, Decimal | None]:
    """Возвращает (work_price, material_price, purchase_price_snapshot).

    Цены фиксируются на момент добавления позиции.
    """
    prices = latest_prices_for(db, [item.id]).get(item.id, {})

    sell_level_id = client.default_price_level_id if client else None
    if sell_level_id is None:
        first = db.scalars(
            select(PriceLevel).order_by(PriceLevel.sort_order, PriceLevel.id)
        ).first()
        sell_level_id = first.id if first else None
    sell = prices.get(sell_level_id, Decimal("0")) if sell_level_id is not None else Decimal("0")

    zakupka = db.scalars(
        select(PriceLevel).where(PriceLevel.name == ZAKUPKA_LEVEL_NAME)
    ).first()
    purchase = prices.get(zakupka.id) if zakupka is not None else None

    if item.kind == "work":
        return sell, Decimal("0"), purchase
    return Decimal("0"), sell, purchase
