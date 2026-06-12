from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier


def test_catalog_models_roundtrip(db_session):
    level = PriceLevel(name="Закупка", sort_order=1)
    supplier = Supplier(name="Bolid")
    db_session.add_all([level, supplier])
    db_session.commit()

    price_list = PriceList(supplier_id=supplier.id, filename="bolid.xlsx", version=1)
    item = CatalogItem(supplier_id=supplier.id, name="С2000-М", article="004432")
    db_session.add_all([price_list, item])
    db_session.commit()

    price = ItemPrice(
        item_id=item.id,
        price_list_id=price_list.id,
        price_level_id=level.id,
        value=Decimal("12721.31"),
    )
    db_session.add(price)
    db_session.commit()
    db_session.refresh(price)

    assert price.value == Decimal("12721.31")
    assert item.kind == "material"
    assert item.unit == "шт"
    assert supplier.column_mapping_template is None
    assert price_list.imported_at is not None


def test_invalid_kind_rejected(db_session):
    supplier = Supplier(name="S")
    db_session.add(supplier)
    db_session.commit()
    db_session.add(CatalogItem(supplier_id=supplier.id, name="X", kind="service"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
