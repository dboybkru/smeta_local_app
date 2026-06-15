from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.catalog.models import CatalogItem, PriceLevel
from app.catalog.service import latest_prices_for
from app.estimates import models, schemas


def visible_estimates(db: Session, user: User):
    """Estimator видит свои; admin/viewer — все в своей org."""
    query = (
        select(models.Estimate)
        .where(models.Estimate.org_id == user.org_id)
        .order_by(models.Estimate.created_at.desc())
    )
    if user.role == "estimator":
        query = query.where(models.Estimate.owner_id == user.id)
    return db.scalars(query).all()


def get_owned_estimate(db: Session, estimate_id: int, user: User) -> models.Estimate:
    """Смета, которую пользователь может ЧИТАТЬ, иначе 404.
    Org isolation first (404, не 403), затем estimator — только свои."""
    est = db.get(models.Estimate, estimate_id)
    if est is None or est.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    return est


def list_clients(db: Session, org_id: int) -> list[models.Client]:
    return db.scalars(
        select(models.Client)
        .where(models.Client.org_id == org_id)
        .order_by(models.Client.name)
    ).all()


def get_client_for_org(db: Session, client_id: int, org_id: int) -> models.Client:
    """Клиент в рамках org, иначе 404 (не 403 — не раскрываем существование)."""
    c = db.get(models.Client, client_id)
    if c is None or c.org_id != org_id:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return c


def create_client(db: Session, data: "schemas.ClientIn", org_id: int) -> models.Client:
    dumped = data.model_dump()
    price_level_id = dumped.get("default_price_level_id")
    if price_level_id is not None:
        level = db.get(PriceLevel, price_level_id)
        if level is None or level.org_id != org_id:
            raise HTTPException(status_code=404, detail="Уровень цен не найден")
    client = models.Client(**dumped, org_id=org_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


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
    if est is None or est.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    return section


def get_owned_line(db: Session, line_id: int, user: User) -> models.EstimateLine:
    line = db.get(models.EstimateLine, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    est = line.section.branch.estimate
    if est is None or est.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    if user.role == "estimator" and est.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    return line


_CENTS = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def compute_totals(est: models.Estimate) -> dict:
    """Все разделы всех веток сметы. Деньги — квантованный Decimal."""
    sections_out = []
    subtotal = Decimal("0")
    sub_materials = Decimal("0")
    sub_works = Decimal("0")
    est_purchase = Decimal("0")

    for branch in est.branches:
        for section in branch.sections:
            materials = sum((ln.material_price * ln.qty for ln in section.lines), Decimal("0"))
            works = sum((ln.work_price * ln.qty for ln in section.lines), Decimal("0"))
            purchase = sum(
                (ln.purchase_price_snapshot * ln.qty
                 for ln in section.lines if ln.purchase_price_snapshot is not None),
                Decimal("0"),
            )
            factor = Decimal("1") + section.markup_percent / Decimal("100")
            materials_sell = materials * factor
            works_sell = works * factor
            sect_total = materials_sell + works_sell
            sect_margin = sect_total - purchase

            sections_out.append({
                "section_id": section.id,
                "materials": _q(materials_sell),
                "works": _q(works_sell),
                "total": _q(sect_total),
                "purchase": _q(purchase),
                "margin": _q(sect_margin),
            })
            subtotal += sect_total
            sub_materials += materials_sell
            sub_works += works_sell
            est_purchase += purchase

    vat = subtotal * est.vat_rate / Decimal("100") if est.vat_enabled else Decimal("0")
    return {
        "sections": sections_out,
        "materials": _q(sub_materials),
        "works": _q(sub_works),
        "subtotal": _q(subtotal),
        "vat": _q(vat),
        "total": _q(subtotal + vat),
        "purchase": _q(est_purchase),
        "margin": _q(subtotal - est_purchase),
    }


def base_branch(est: models.Estimate) -> models.EstimateBranch:
    """Единственная базовая ветка (варианты отложены)."""
    if not est.branches:
        raise HTTPException(status_code=400, detail="У сметы нет ветки")
    return est.branches[0]


ZAKUPKA_LEVEL_NAME = "Закупка"


def snapshot_line_values(
    db: Session,
    item: CatalogItem,
    client: models.Client | None,
    org_id: int,
) -> tuple[Decimal, Decimal, Decimal | None]:
    """Возвращает (work_price, material_price, purchase_price_snapshot).

    Цены фиксируются на момент добавления позиции.
    org_id используется для скоупинга уровней цен в рамках org.
    """
    prices = latest_prices_for(db, [item.id]).get(item.id, {})

    sell_level_id = client.default_price_level_id if client else None
    if sell_level_id is None:
        q = (
            select(PriceLevel)
            .where(PriceLevel.org_id == org_id)
            .order_by(PriceLevel.sort_order, PriceLevel.id)
        )
        first = db.scalars(q).first()
        sell_level_id = first.id if first else None
    sell = prices.get(sell_level_id, Decimal("0")) if sell_level_id is not None else Decimal("0")

    q_zak = select(PriceLevel).where(
        PriceLevel.name == ZAKUPKA_LEVEL_NAME, PriceLevel.org_id == org_id
    )
    zakupka = db.scalars(q_zak).first()
    purchase = prices.get(zakupka.id) if zakupka is not None else None

    if item.kind == "work":
        return sell, Decimal("0"), purchase
    return Decimal("0"), sell, purchase


def build_estimate_detail(est: models.Estimate, user: User) -> "schemas.EstimateDetail":
    """Деталь сметы с роле-зависимым сокрытием маржи/закупки (общий код для get/apply)."""
    can_see_margin = (
        user.role == "org_admin" or user.is_superuser or est.owner_id == user.id
    )
    totals = compute_totals(est)
    if not can_see_margin:
        for s in totals["sections"]:
            s["purchase"] = None
            s["margin"] = None
        totals["purchase"] = None
        totals["margin"] = None
    detail = schemas.EstimateDetail.model_validate(est)
    detail.totals = schemas.EstimateTotals(**totals)
    if not can_see_margin:
        for branch in detail.branches:
            for section in branch.sections:
                for line in section.lines:
                    line.purchase_price_snapshot = None
    return detail
