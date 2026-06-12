from decimal import Decimal

from app.catalog.importer import ParsedRow, import_parsed
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier


def setup_base(db):
    supplier = Supplier(name="Bolid")
    level = PriceLevel(name="Розница")
    db.add_all([supplier, level])
    db.commit()
    return supplier, level


def test_first_import_creates_everything(db_session):
    supplier, level = setup_base(db_session)
    parsed = [
        ParsedRow(name="Сириус", article="1-520-887", prices={level.id: Decimal("36159.53")}),
        ParsedRow(name="С2000-М", article="110-058", prices={level.id: Decimal("12721.31")}),
    ]
    summary = import_parsed(db_session, supplier.id, "bolid.xlsx", parsed, kind="material")
    assert summary.version == 1
    assert summary.items_created == 2
    assert summary.items_updated == 0
    assert summary.prices_written == 2
    assert summary.price_changes == 0
    assert db_session.query(CatalogItem).count() == 2
    assert db_session.query(ItemPrice).count() == 2


def test_second_import_new_version_and_delta(db_session):
    supplier, level = setup_base(db_session)
    import_parsed(
        db_session,
        supplier.id,
        "v1.xlsx",
        [ParsedRow(name="Сириус", article="A1", prices={level.id: Decimal("100.00")})],
        kind="material",
    )
    summary = import_parsed(
        db_session,
        supplier.id,
        "v2.xlsx",
        [
            ParsedRow(name="Сириус", article="A1", prices={level.id: Decimal("112.00")}),
            ParsedRow(name="Новый", article="A2", prices={level.id: Decimal("50.00")}),
        ],
        kind="material",
    )
    assert summary.version == 2
    assert summary.items_created == 1
    assert summary.items_updated == 1
    assert summary.price_changes == 1  # 100 -> 112
    assert db_session.query(PriceList).count() == 2
    # история сохранена: обе цены Сириуса лежат в разных прайс-листах
    assert db_session.query(ItemPrice).count() == 3


def test_upsert_by_name_when_no_article(db_session):
    supplier, level = setup_base(db_session)
    import_parsed(
        db_session,
        supplier.id,
        "w1.xlsx",
        [ParsedRow(name="Монтаж камеры", prices={level.id: Decimal("3500")})],
        kind="work",
    )
    import_parsed(
        db_session,
        supplier.id,
        "w2.xlsx",
        [ParsedRow(name="Монтаж камеры", prices={level.id: Decimal("3700")})],
        kind="work",
    )
    items = db_session.query(CatalogItem).all()
    assert len(items) == 1
    assert items[0].kind == "work"


def test_rows_with_problems_are_skipped(db_session):
    supplier, level = setup_base(db_session)
    parsed = [
        ParsedRow(name="Норм", article="A1", prices={level.id: Decimal("10")}),
        ParsedRow(name="Битый", article="A2", problems=["Нет ни одной цены"]),
    ]
    summary = import_parsed(db_session, supplier.id, "f.xlsx", parsed, kind="material")
    assert summary.items_created == 1
    assert summary.rows_skipped == 1


def test_duplicate_rows_in_one_file_skipped(db_session):
    supplier, level = setup_base(db_session)
    parsed = [
        ParsedRow(name="Сириус", article="A1", prices={level.id: Decimal("100.00")}),
        ParsedRow(name="Сириус дубль", article="A1", prices={level.id: Decimal("200.00")}),
    ]
    summary = import_parsed(db_session, supplier.id, "f.xlsx", parsed, kind="material")
    assert summary.items_created == 1
    assert summary.rows_skipped == 1
    assert summary.prices_written == 1
