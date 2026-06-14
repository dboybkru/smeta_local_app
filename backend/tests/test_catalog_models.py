from app.catalog.models import CatalogItem, Supplier


def test_catalog_item_new_fields_defaults(db_session):
    sup = Supplier(name="S"); db_session.add(sup); db_session.commit()
    it = CatalogItem(supplier_id=sup.id, name="Камера")
    db_session.add(it); db_session.commit(); db_session.refresh(it)
    assert it.manufacturer is None
    assert it.price_on_request is False


def test_catalog_item_set_new_fields(db_session):
    sup = Supplier(name="S2"); db_session.add(sup); db_session.commit()
    it = CatalogItem(supplier_id=sup.id, name="Камера", manufacturer="Optimus",
                     price_on_request=True)
    db_session.add(it); db_session.commit(); db_session.refresh(it)
    assert it.manufacturer == "Optimus"
    assert it.price_on_request is True
