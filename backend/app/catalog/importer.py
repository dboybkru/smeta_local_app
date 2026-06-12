"""Применение маппинга к строкам файла и нормализация значений."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.models import CatalogItem, ItemPrice, PriceList
from app.catalog.parser import Rows
from app.catalog.schemas import ColumnMapping


@dataclass
class ParsedRow:
    name: str
    article: str = ""
    unit: str = "шт"
    category: str = ""
    prices: dict[int, Decimal] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


@dataclass
class ImportSummary:
    price_list_id: int
    version: int
    items_created: int = 0
    items_updated: int = 0
    prices_written: int = 0
    price_changes: int = 0
    rows_skipped: int = 0


def _cell(row: list, index: int | None) -> str:
    if index is None or index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


def _parse_price(raw: str) -> Decimal:
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(",", ".")
    return Decimal(cleaned).quantize(Decimal("0.01"))


def parse_rows(
    rows: Rows,
    header_row: int,
    mapping: ColumnMapping,
    default_category: str = "",
) -> list[ParsedRow]:
    header = rows[header_row] if header_row < len(rows) else []
    header_name = _cell(header, mapping.name_col)
    parsed: list[ParsedRow] = []
    for row in rows[header_row + 1 :]:
        name = _cell(row, mapping.name_col)
        if not name:
            continue
        if name == header_name:  # повтор шапки посреди листа (реальные прайсы Optimus)
            continue
        item = ParsedRow(
            name=name,
            article=_cell(row, mapping.article_col),
            unit=_cell(row, mapping.unit_col) or "шт",
            category=_cell(row, mapping.category_col) or default_category,
        )
        for level_id, col in mapping.price_cols.items():
            raw = _cell(row, col)
            if not raw:
                continue
            try:
                value = _parse_price(raw)
            except InvalidOperation:
                item.problems.append(f"Цена не распознана: «{raw}» (колонка {col + 1})")
                continue
            if value < 0:
                item.problems.append(f"Отрицательная цена: {value} (колонка {col + 1})")
                continue
            item.prices[level_id] = value
        if mapping.price_cols and not item.prices and not item.problems:
            item.problems.append("Нет ни одной цены")
        parsed.append(item)
    return parsed


def _latest_prices(db: Session, supplier_id: int) -> dict[tuple[int, int], Decimal]:
    """{(item_id, level_id): value} из последнего прайс-листа поставщика."""
    last = db.scalar(
        select(PriceList)
        .where(PriceList.supplier_id == supplier_id)
        .order_by(PriceList.version.desc())
        .limit(1)
    )
    if last is None:
        return {}
    rows = db.execute(
        select(ItemPrice.item_id, ItemPrice.price_level_id, ItemPrice.value).where(
            ItemPrice.price_list_id == last.id
        )
    ).all()
    return {(item_id, level_id): value for item_id, level_id, value in rows}


def _find_item(db: Session, supplier_id: int, row: ParsedRow) -> CatalogItem | None:
    """Upsert-ключ: артикул, если он есть, иначе имя (см. комментарий в models.CatalogItem)."""
    query = select(CatalogItem).where(CatalogItem.supplier_id == supplier_id)
    if row.article:
        query = query.where(CatalogItem.article == row.article)
    else:
        query = query.where(CatalogItem.article == "", CatalogItem.name == row.name)
    return db.scalar(query.limit(1))


def import_parsed(
    db: Session,
    supplier_id: int,
    filename: str,
    parsed: list[ParsedRow],
    kind: str,
) -> ImportSummary:
    previous = _latest_prices(db, supplier_id)
    version = (
        db.scalar(
            select(func.max(PriceList.version)).where(PriceList.supplier_id == supplier_id)
        )
        or 0
    ) + 1
    price_list = PriceList(supplier_id=supplier_id, filename=filename, version=version)
    db.add(price_list)
    db.flush()

    summary = ImportSummary(price_list_id=price_list.id, version=version)
    for row in parsed:
        if row.problems:
            summary.rows_skipped += 1
            continue
        item = _find_item(db, supplier_id, row)
        if item is None:
            item = CatalogItem(
                supplier_id=supplier_id,
                name=row.name,
                article=row.article,
                unit=row.unit,
                category=row.category,
                kind=kind,
            )
            db.add(item)
            db.flush()
            summary.items_created += 1
        else:
            item.unit = row.unit
            item.category = row.category or item.category
            summary.items_updated += 1
        for level_id, value in row.prices.items():
            db.add(
                ItemPrice(
                    item_id=item.id,
                    price_list_id=price_list.id,
                    price_level_id=level_id,
                    value=value,
                )
            )
            summary.prices_written += 1
            old = previous.get((item.id, level_id))
            if old is not None and old != value:
                summary.price_changes += 1
    db.commit()
    return summary
