"""Поиск по каталогу и выборка актуальных цен."""

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.catalog import search
from app.catalog.models import CatalogItem, ItemPrice, PriceList

# TODO(scale): при росте каталога заменить LIKE на tsvector+pg_trgm (спека §4)


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_items(
    db: Session,
    q: str = "",
    supplier_id: int | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CatalogItem], int]:
    query = select(CatalogItem)
    for token in search.tokens(q):
        # токен matches, если ЛЮБОЙ его раскладочный вариант — подстрока name/article
        variant_clauses = []
        for v in search.variants(token):
            pat = f"%{_escape_like(v)}%"
            variant_clauses.append(func.lower(CatalogItem.name).like(pat, escape="\\"))
            variant_clauses.append(func.lower(CatalogItem.article).like(pat, escape="\\"))
        query = query.where(or_(*variant_clauses))
    if supplier_id is not None:
        query = query.where(CatalogItem.supplier_id == supplier_id)
    if kind is not None:
        query = query.where(CatalogItem.kind == kind)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(query.order_by(CatalogItem.name).limit(limit).offset(offset)).all()
    )
    return items, total


def latest_prices_for(db: Session, item_ids: list[int]) -> dict[int, dict[int, Decimal]]:
    """{item_id: {price_level_id: value}} — цена из самого свежего прайс-листа на пару."""
    if not item_ids:
        return {}
    latest_version = (
        select(
            ItemPrice.item_id,
            ItemPrice.price_level_id,
            func.max(PriceList.version).label("max_version"),
        )
        .join(PriceList, PriceList.id == ItemPrice.price_list_id)
        .where(ItemPrice.item_id.in_(item_ids))
        .group_by(ItemPrice.item_id, ItemPrice.price_level_id)
        .subquery()
    )
    rows = db.execute(
        select(ItemPrice.item_id, ItemPrice.price_level_id, ItemPrice.value)
        .join(PriceList, PriceList.id == ItemPrice.price_list_id)
        .join(
            latest_version,
            (ItemPrice.item_id == latest_version.c.item_id)
            & (ItemPrice.price_level_id == latest_version.c.price_level_id)
            & (PriceList.version == latest_version.c.max_version),
        )
    ).all()
    result: dict[int, dict[int, Decimal]] = {}
    for item_id, level_id, value in rows:
        result.setdefault(item_id, {})[level_id] = value
    return result
