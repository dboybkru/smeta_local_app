from app.auth.models import User
from app.catalog.models import CatalogItem, Supplier
from app.catalog.service import search_items
from app.core.security import create_access_token


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _items(db):
    sup = Supplier(name="S"); db.add(sup); db.commit()
    db.add_all([
        CatalogItem(supplier_id=sup.id, name="Камера A", article="1", unit="шт", kind="material",
                    characteristics={"Разрешение": "2 Мп", "Питание": "PoE"}),
        CatalogItem(supplier_id=sup.id, name="Камера B", article="2", unit="шт", kind="material",
                    characteristics={"Разрешение": "4 Мп", "Питание": "PoE"}),
    ])
    db.commit(); return sup


def test_search_items_facet_filter(db_session):
    _items(db_session)
    items, total = search_items(db_session, facets={"Разрешение": "2 Мп"})
    assert total == 1 and items[0].name == "Камера A"


def test_facets_endpoint_aggregates(client, db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    _items(db_session)
    body = client.get("/api/catalog/facets", headers=_hdr(u)).json()
    assert sorted(body["Разрешение"]) == ["2 Мп", "4 Мп"]
    assert body["Питание"] == ["PoE"]


def test_items_endpoint_facet_param(client, db_session):
    u = User(email="u2@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    _items(db_session)
    body = client.get("/api/catalog/items?f=Разрешение=4 Мп", headers=_hdr(u)).json()
    assert body["total"] == 1 and body["items"][0]["name"] == "Камера B"
