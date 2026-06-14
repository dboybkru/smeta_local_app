from decimal import Decimal

from sqlalchemy import select

from app.catalog.importer import ParsedRow, import_parsed
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, Supplier


def _supplier_level(db):
    sup = Supplier(name="Опт-С"); db.add(sup); db.commit()
    lvl = PriceLevel(name="Розница"); db.add(lvl); db.commit()
    return sup, lvl


def test_import_writes_manufacturer_and_on_request(db_session):
    sup, lvl = _supplier_level(db_session)
    parsed = [
        ParsedRow(name="Камера", article="A1", manufacturer="Optimus",
                  price_on_request=True, prices={lvl.id: Decimal("0.00")}),
    ]
    import_parsed(db_session, sup.id, "p.xlsx", parsed, kind="material")
    item = db_session.scalars(select(CatalogItem)).one()
    assert item.manufacturer == "Optimus"
    assert item.price_on_request is True
    price = db_session.scalars(select(ItemPrice)).one()
    assert price.value == Decimal("0.00")


def test_import_updates_on_request_flag(db_session):
    sup, lvl = _supplier_level(db_session)
    import_parsed(db_session, sup.id, "p.xlsx",
                  [ParsedRow(name="К", article="A1", price_on_request=True,
                             prices={lvl.id: Decimal("0")})], kind="material")
    import_parsed(db_session, sup.id, "p2.xlsx",
                  [ParsedRow(name="К", article="A1", manufacturer="X",
                             price_on_request=False, prices={lvl.id: Decimal("99")})],
                  kind="material")
    item = db_session.scalars(select(CatalogItem)).one()
    assert item.price_on_request is False
    assert item.manufacturer == "X"
