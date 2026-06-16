from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier
from tests.orghelpers import get_or_create_org as _get_or_create_org


def test_catalog_models_roundtrip(db_session):
    org = _get_or_create_org(db_session)
    level = PriceLevel(name="Закупка", sort_order=1, org_id=org.id)
    supplier = Supplier(name="Bolid", org_id=org.id)
    db_session.add_all([level, supplier])
    db_session.commit()

    price_list = PriceList(supplier_id=supplier.id, filename="bolid.xlsx", version=1, org_id=org.id)
    item = CatalogItem(supplier_id=supplier.id, name="С2000-М", article="004432", org_id=org.id)
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
    org = _get_or_create_org(db_session)
    supplier = Supplier(name="S", org_id=org.id)
    db_session.add(supplier)
    db_session.commit()
    db_session.add(CatalogItem(supplier_id=supplier.id, name="X", kind="service", org_id=org.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_catalog_item_new_fields_defaults(db_session):
    org = _get_or_create_org(db_session)
    sup = Supplier(name="S", org_id=org.id); db_session.add(sup); db_session.commit()
    it = CatalogItem(supplier_id=sup.id, name="Камера", org_id=org.id)
    db_session.add(it); db_session.commit(); db_session.refresh(it)
    assert it.manufacturer is None
    assert it.price_on_request is False


def test_catalog_item_set_new_fields(db_session):
    org = _get_or_create_org(db_session)
    sup = Supplier(name="S2", org_id=org.id); db_session.add(sup); db_session.commit()
    it = CatalogItem(
        supplier_id=sup.id, name="Камера", manufacturer="Optimus",
        price_on_request=True, org_id=org.id,
    )
    db_session.add(it); db_session.commit(); db_session.refresh(it)
    assert it.manufacturer == "Optimus"
    assert it.price_on_request is True
