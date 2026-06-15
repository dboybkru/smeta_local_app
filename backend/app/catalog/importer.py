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
    characteristics: str = ""
    manufacturer: str = ""
    price_on_request: bool = False
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
    problems: list[str] = field(default_factory=list)


def _cell(row: list, index: int | None) -> str:
    if index is None or index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


def _parse_price(raw: str) -> Decimal:
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(",", ".")
    return Decimal(cleaned).quantize(Decimal("0.01"))


ON_REQUEST_PHRASES = ("звоните", "по запросу", "уточняйте", "уточнить",
                      "договорная", "запрос", "прайс")


def _clean_unit(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "шт"
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1].strip()
    return raw or "шт"


def _is_on_request_text(raw: str) -> bool:
    low = raw.strip().lower()
    return any(p in low for p in ON_REQUEST_PHRASES)


def _category_text(row: list, mapping: ColumnMapping) -> str:
    """Текст строки-категории: имя, иначе производитель, иначе любая описательная."""
    for col in (mapping.name_col, mapping.manufacturer_col, mapping.characteristics_col):
        if col is not None:
            t = _cell(row, col)
            if t:
                return t
    for cell in row:
        if cell is not None and str(cell).strip() and not str(cell).strip().isdigit():
            return str(cell).strip()
    return ""


def parse_rows(rows: Rows, mapping: ColumnMapping, default_category: str = "") -> list[ParsedRow]:
    data_start = mapping.data_start_row if mapping.data_start_row is not None \
        else mapping.header_row + 1
    on_request_cols = set(mapping.on_request_cols)
    header_name = ""
    if 0 <= mapping.header_row < len(rows):
        header_name = _cell(rows[mapping.header_row], mapping.name_col)
    parsed: list[ParsedRow] = []
    current_category = ""
    for row in rows[data_start:]:
        name = _cell(row, mapping.name_col)
        if name and header_name and name == header_name:
            continue
        prices: dict[int, Decimal] = {}
        on_request = False
        price_problems: list[str] = []
        for level_id, col in mapping.price_cols.items():
            raw = _cell(row, col)
            if not raw:
                continue
            if col in on_request_cols or _is_on_request_text(raw):
                prices[level_id] = Decimal("0.00")
                on_request = True
                continue
            try:
                value = _parse_price(raw)
            except InvalidOperation:
                price_problems.append(f"Цена не распознана: «{raw}» (колонка {col + 1})")
                continue
            if value < 0:
                price_problems.append(f"Отрицательная цена: {value} (колонка {col + 1})")
                continue
            prices[level_id] = value

        has_article = bool(_cell(row, mapping.article_col))
        if not prices and not price_problems:
            if not has_article:
                # строка без артикула и без цен — категория или пустая
                text = _category_text(row, mapping)
                if text:
                    current_category = text
                continue
            if not name:
                continue
            item = _build_row(row, mapping, name, current_category, default_category,
                              prices, on_request)
            if mapping.price_cols:
                # ценовые колонки настроены, но в этой строке цен нет — это проблема
                item.problems.append("Нет ни одной цены")
            parsed.append(item)
            continue

        if not name:
            continue
        item = _build_row(row, mapping, name, current_category, default_category,
                          prices, on_request)
        item.problems.extend(price_problems)
        parsed.append(item)
    return parsed


def _build_row(row, mapping, name, current_category, default_category, prices,
               on_request) -> ParsedRow:
    category = (current_category or _cell(row, mapping.category_col) or default_category)
    return ParsedRow(
        name=name,
        article=_cell(row, mapping.article_col),
        unit=_clean_unit(_cell(row, mapping.unit_col)),
        category=category,
        characteristics=_cell(row, mapping.characteristics_col),
        manufacturer=_cell(row, mapping.manufacturer_col),
        price_on_request=on_request,
        prices=prices,
    )


def _latest_prices(
    db: Session, supplier_id: int, org_id: int | None = None
) -> dict[tuple[int, int], Decimal]:
    """{(item_id, level_id): value} из последнего прайс-листа поставщика."""
    q = (
        select(PriceList)
        .where(PriceList.supplier_id == supplier_id)
    )
    if org_id is not None:
        q = q.where(PriceList.org_id == org_id)
    last = db.scalar(q.order_by(PriceList.version.desc()).limit(1))
    if last is None:
        return {}
    rows = db.execute(
        select(ItemPrice.item_id, ItemPrice.price_level_id, ItemPrice.value).where(
            ItemPrice.price_list_id == last.id
        )
    ).all()
    return {(item_id, level_id): value for item_id, level_id, value in rows}


def _find_item(
    db: Session, supplier_id: int, row: ParsedRow, org_id: int | None = None
) -> CatalogItem | None:
    """Upsert-ключ: артикул, если он есть, иначе имя (см. комментарий в models.CatalogItem)."""
    query = select(CatalogItem).where(CatalogItem.supplier_id == supplier_id)
    if org_id is not None:
        query = query.where(CatalogItem.org_id == org_id)
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
    org_id: int | None = None,
) -> ImportSummary:
    previous = _latest_prices(db, supplier_id, org_id=org_id)
    q = select(func.max(PriceList.version)).where(PriceList.supplier_id == supplier_id)
    if org_id is not None:
        q = q.where(PriceList.org_id == org_id)
    version = (db.scalar(q) or 0) + 1
    price_list = PriceList(supplier_id=supplier_id, filename=filename, version=version,
                           **({"org_id": org_id} if org_id is not None else {}))
    db.add(price_list)
    db.flush()

    summary = ImportSummary(price_list_id=price_list.id, version=version)
    seen_keys: set[tuple[str, str]] = set()
    for row in parsed:
        if row.problems:
            summary.rows_skipped += 1
            summary.problems.append(f"{row.name}: {'; '.join(row.problems)}")
            continue
        key = ("a", row.article) if row.article else ("n", row.name)
        if key in seen_keys:
            row.problems.append("Дубликат строки в файле — пропущена")
            summary.rows_skipped += 1
            summary.problems.append(f"{row.name}: {'; '.join(row.problems)}")
            continue
        seen_keys.add(key)
        item = _find_item(db, supplier_id, row, org_id=org_id)
        if item is None:
            item_kwargs: dict = dict(
                supplier_id=supplier_id,
                name=row.name,
                article=row.article,
                unit=row.unit,
                category=row.category,
                kind=kind,
                manufacturer=row.manufacturer or None,
                price_on_request=row.price_on_request,
                characteristics_raw=row.characteristics or None,
            )
            if org_id is not None:
                item_kwargs["org_id"] = org_id
            item = CatalogItem(**item_kwargs)
            db.add(item)
            db.flush()
            summary.items_created += 1
        else:
            item.unit = row.unit
            item.category = row.category or item.category
            item.manufacturer = row.manufacturer or item.manufacturer
            item.price_on_request = row.price_on_request
            if row.characteristics and row.characteristics != item.characteristics_raw:
                item.characteristics_raw = row.characteristics
                item.characteristics = None  # сырьё изменилось → переизвлечь признаки
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
