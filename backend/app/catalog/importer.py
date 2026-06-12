"""Применение маппинга к строкам файла и нормализация значений."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

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
                item.prices[level_id] = _parse_price(raw)
            except InvalidOperation:
                item.problems.append(f"Цена не распознана: «{raw}» (колонка {col + 1})")
        if mapping.price_cols and not item.prices and not item.problems:
            item.problems.append("Нет ни одной цены")
        parsed.append(item)
    return parsed
