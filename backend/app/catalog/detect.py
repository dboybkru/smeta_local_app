"""Авто-определение раскладки прайс-листа по подписям колонок."""

from dataclasses import dataclass, field

from app.catalog.parser import Rows

SCAN_LIMIT = 20

ROLE_SYNONYMS: dict[str, list[str]] = {
    "name": ["наименование работы", "наименование", "название", "товар"],
    "article": ["артикул", "код товара", "код"],
    "chars": ["краткая характеристика", "краткие характеристики",
              "характеристики", "характеристика", "описание"],
    "unit": ["ед. изм", "ед.изм", "вал./ед. изм", "единица", "ед изм"],
    "manufacturer": ["производитель", "бренд", "вендор"],
}
PRICE_WORDS = ["розничная", "розн", "оптовая", "опт", "кр.опт", "кр опт",
               "парт", "инст", "цена", "стоимость"]
GENERIC_PRICE = {"цены", "цены руб", "цены, руб", "цена руб"}


@dataclass
class PriceColumn:
    index: int
    label: str
    sample: str = ""
    on_request: bool = False


@dataclass
class DetectedLayout:
    header_row: int
    data_start_row: int
    name_col: int | None = None
    article_col: int | None = None
    chars_col: int | None = None
    unit_col: int | None = None
    manufacturer_col: int | None = None
    price_columns: list[PriceColumn] = field(default_factory=list)
    confidence: float = 0.0


def _norm(cell: object) -> str:
    if cell is None:
        return ""
    s = str(cell).strip().lower().replace("ё", "е")
    s = " ".join(s.split())
    return s.rstrip(".:")


def _is_price_word(norm: str) -> bool:
    return any(w in norm for w in PRICE_WORDS)


def _on_request_label(norm: str) -> bool:
    return any(t in norm for t in ("у.е", "у. е", "усл", "y.e"))


def _match_role(norm: str) -> tuple[str, int] | None:
    for role, syns in ROLE_SYNONYMS.items():
        for rank, s in enumerate(syns):
            if s in norm:
                return role, rank
    return None


def _score_row(row: list) -> int:
    score = 0
    has_name = has_price = False
    for cell in row:
        norm = _norm(cell)
        if not norm:
            continue
        m = _match_role(norm)
        if m:
            score += 1
            if m[0] == "name":
                has_name = True
        elif _is_price_word(norm) or norm in GENERIC_PRICE:
            score += 1
            has_price = True
    return score if (has_name and has_price) else 0


def _find_header_row(rows: Rows, scan_limit: int) -> int | None:
    best_row, best_score = None, 0
    for i, row in enumerate(rows[:scan_limit]):
        s = _score_row(row)
        if s > best_score:
            best_row, best_score = i, s
    return best_row


def _assign_roles(header: list) -> dict[str, int]:
    roles: dict[str, tuple[int, int]] = {}
    for col, cell in enumerate(header):
        norm = _norm(cell)
        if not norm:
            continue
        m = _match_role(norm)
        if m is None:
            continue
        role, rank = m
        prev = roles.get(role)
        if prev is None or rank < prev[1]:
            roles[role] = (col, rank)
    return {role: col for role, (col, _rank) in roles.items()}


def _sample(rows: Rows, data_start: int, col: int) -> str:
    for row in rows[data_start:data_start + 5]:
        if col < len(row) and row[col] is not None and str(row[col]).strip():
            return str(row[col]).strip()
    return ""


def _generic_price_col(header: list) -> int | None:
    for col, cell in enumerate(header):
        if _norm(cell) in GENERIC_PRICE:
            return col
    return None


def _is_two_row(rows: Rows, header_row: int) -> bool:
    header = rows[header_row]
    gen = _generic_price_col(header)
    if gen is None or header_row + 1 >= len(rows):
        return False
    sub = rows[header_row + 1]
    # Cells before the generic price column must be empty (sub-label row, not data row)
    if any(c is not None and str(c).strip() for c in sub[:gen]):
        return False
    return any(c is not None and str(c).strip() for c in sub[gen:])


def _detect_price_columns(rows: Rows, header_row: int) -> list[PriceColumn]:
    header = rows[header_row]
    if _is_two_row(rows, header_row):
        gen = _generic_price_col(header)
        on_req = _on_request_label(_norm(header[gen]))
        sub = rows[header_row + 1]
        out: list[PriceColumn] = []
        for col in range(gen, len(sub)):
            val = sub[col]
            if val is not None and str(val).strip():
                out.append(PriceColumn(index=col, label=f"Цена {str(val).strip()}",
                                       on_request=on_req))
        return out
    out = []
    for col, cell in enumerate(header):
        norm = _norm(cell)
        if not norm or _match_role(norm):
            continue
        if _is_price_word(norm) or norm in GENERIC_PRICE:
            out.append(PriceColumn(index=col, label=str(cell).strip(),
                                   on_request=_on_request_label(norm)))
    return out


def detect_layout(rows: Rows, scan_limit: int = SCAN_LIMIT) -> DetectedLayout | None:
    header_row = _find_header_row(rows, scan_limit)
    if header_row is None:
        return None
    header = rows[header_row]
    roles = _assign_roles(header)
    two_row = _is_two_row(rows, header_row)
    data_start = header_row + 2 if two_row else header_row + 1
    price_columns = _detect_price_columns(rows, header_row)
    for pc in price_columns:
        pc.sample = _sample(rows, data_start, pc.index)
    layout = DetectedLayout(
        header_row=header_row,
        data_start_row=data_start,
        name_col=roles.get("name"),
        article_col=roles.get("article"),
        chars_col=roles.get("chars"),
        unit_col=roles.get("unit"),
        manufacturer_col=roles.get("manufacturer"),
        price_columns=price_columns,
    )
    nonempty = sum(1 for c in header if _norm(c))
    matched = len(roles) + len(price_columns)
    layout.confidence = round(matched / nonempty, 2) if nonempty else 0.0
    return layout
