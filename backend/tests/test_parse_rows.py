from decimal import Decimal

from app.catalog.importer import parse_rows
from app.catalog.schemas import ColumnMapping
from tests.fixtures import pricelists as P


def test_bolid_products_with_two_prices():
    m = ColumnMapping(name_col=0, characteristics_col=1, article_col=3,
                      header_row=0, data_start_row=1, price_cols={10: 5, 11: 6})
    rows = parse_rows(P.BOLID, m)
    assert len(rows) == 2
    assert rows[0].name == "Сириус"
    assert rows[0].article == "1-520-887-052"
    assert rows[0].prices == {10: Decimal("36159.53"), 11: Decimal("33378.03")}
    assert rows[0].price_on_request is False


def test_kontrol_category_capture_and_zvonite():
    m = ColumnMapping(name_col=2, characteristics_col=3, manufacturer_col=1,
                      header_row=1, data_start_row=3, price_cols={10: 4, 11: 5, 12: 6})
    rows = parse_rows(P.KONTROL, m)
    assert [r.name for r in rows] == ["CNC-02-IP", "NMI-08"]
    r = rows[0]
    assert r.manufacturer == "Parsec"
    assert r.category == "Интегрированная система"
    assert r.prices[10] == Decimal("24864")
    assert r.prices[12] == Decimal("0")
    assert r.price_on_request is True


def test_pricetin_unit_from_text_and_category():
    m = ColumnMapping(name_col=3, article_col=2, characteristics_col=4,
                      manufacturer_col=5, unit_col=6, header_row=4, data_start_row=6,
                      price_cols={10: 7, 11: 8, 12: 9})
    rows = parse_rows(P.PRICETIN, m)
    assert [r.name for r in rows] == ["DD-01", "CM-800"]
    assert rows[0].unit == "шт"
    assert rows[0].category == "Извещатели охранные"
    assert rows[0].article == "319298"


def test_akkum_on_request_columns_zero_price():
    m = ColumnMapping(name_col=0, characteristics_col=2, article_col=10,
                      header_row=3, data_start_row=4,
                      price_cols={10: 3, 11: 4}, on_request_cols=[3, 4])
    rows = parse_rows(P.AKKUM, m)
    assert len(rows) == 1
    assert rows[0].prices == {10: Decimal("0"), 11: Decimal("0")}
    assert rows[0].price_on_request is True


def test_product_without_price_has_article_warns():
    data = [["Наименование", "Код", "Цена"],
            ["Болт", "К1", ""]]
    m = ColumnMapping(name_col=0, article_col=1, header_row=0, data_start_row=1,
                      price_cols={10: 2})
    rows = parse_rows(data, m)
    assert len(rows) == 1
    assert rows[0].problems == ["Нет ни одной цены"]


def test_blank_row_skipped_silently():
    data = [["Наименование", "Цена"], [None, None], ["Кабель", "100"]]
    m = ColumnMapping(name_col=0, header_row=0, data_start_row=1, price_cols={10: 1})
    rows = parse_rows(data, m)
    assert [r.name for r in rows] == ["Кабель"]
