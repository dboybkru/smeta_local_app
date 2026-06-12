from decimal import Decimal

from app.catalog.importer import parse_rows
from app.catalog.parser import load_tables
from app.catalog.schemas import ColumnMapping
from tests.catalog_files import make_bolid_csv, make_bolid_xlsx


def test_parse_bolid_two_levels():
    rows = load_tables(make_bolid_xlsx(), "b.xlsx")["Болид"]
    mapping = ColumnMapping(name_col=0, article_col=2, price_cols={1: 3, 2: 4})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert len(parsed) == 3
    first = parsed[0]
    assert first.name == "Сириус"
    assert first.article == "1-520-887"
    assert first.prices == {1: Decimal("36159.53"), 2: Decimal("33378.03")}
    assert first.problems == []


def test_parse_comma_decimal_csv():
    rows = load_tables(make_bolid_csv(), "b.csv")["csv"]
    mapping = ColumnMapping(name_col=0, article_col=1, price_cols={1: 2})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert parsed[0].prices[1] == Decimal("36159.53")


def test_skip_empty_name_rows():
    rows = [["Имя", "Цена"], [None, 100], ["", 100], ["Товар", 50]]
    mapping = ColumnMapping(name_col=0, price_cols={1: 1})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert len(parsed) == 1
    assert parsed[0].name == "Товар"


def test_bad_price_recorded_as_problem():
    rows = [["Имя", "Цена"], ["Товар", "договорная"]]
    mapping = ColumnMapping(name_col=0, price_cols={1: 1})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert parsed[0].prices == {}
    assert "Цена" in parsed[0].problems[0] or "цена" in parsed[0].problems[0]


def test_default_category_and_unit():
    rows = [["Имя", "Цена"], ["Товар", 10]]
    mapping = ColumnMapping(name_col=0, price_cols={1: 1})
    parsed = parse_rows(rows, header_row=0, mapping=mapping, default_category="IP камеры")
    assert parsed[0].category == "IP камеры"
    assert parsed[0].unit == "шт"


def test_repeated_header_rows_skipped():
    rows = [
        ["Имя", "Цена"],
        ["Товар А", 10],
        ["Имя", "Цена"],  # повтор шапки посреди листа
        ["Товар Б", 20],
    ]
    mapping = ColumnMapping(name_col=0, price_cols={1: 1})
    parsed = parse_rows(rows, header_row=0, mapping=mapping)
    assert [p.name for p in parsed] == ["Товар А", "Товар Б"]
