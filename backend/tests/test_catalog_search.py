import json

from app.catalog import search
from app.catalog.models import CatalogItem, Supplier
from app.catalog.service import search_items
from app.orgs.models import Organization
from tests.catalog_files import make_bolid_xlsx
from tests.test_price_levels import make_admin


def _get_or_create_org(db):
    from sqlalchemy import select
    org = db.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db.add(org)
        db.commit()
    return org


def _mk_item(db, name):
    org = _get_or_create_org(db)
    s = Supplier(name=f"S-{name}", org_id=org.id)
    db.add(s)
    db.commit()
    it = CatalogItem(
        supplier_id=s.id, name=name, article="A", unit="шт", kind="material", org_id=org.id
    )
    db.add(it)
    db.commit()
    return it


def test_variants_swaps_layout():
    assert "камера" in search.variants("rfvthf")  # EN-раскладка слова «камера»
    assert "rfvthf" in search.variants("камера")


def test_search_wrong_layout_finds(db_session):
    _mk_item(db_session, "Видеокамера Optimus AHD")
    items, total = search_items(db_session, q="rfvthf")
    assert total == 1 and items[0].name == "Видеокамера Optimus AHD"


def test_search_multiword_any_order(db_session):
    _mk_item(db_session, "Видеокамера Optimus AHD")
    a, _ = search_items(db_session, q="optimus камера")
    b, _ = search_items(db_session, q="камера optimus")
    assert len(a) == 1 and len(b) == 1


def test_search_multiword_no_match(db_session):
    _mk_item(db_session, "Кабель UTP")
    items, total = search_items(db_session, q="камера optimus")
    assert total == 0 and items == []


def import_bolid(client, admin, db_session):
    retail = client.post(
        "/api/price-levels", json={"name": "Розница"}, headers=admin
    ).json()["id"]
    supplier_id = client.post(
        "/api/suppliers", json={"name": "Bolid"}, headers=admin
    ).json()["id"]
    mapping = {"name_col": 0, "article_col": 2, "header_row": 0, "price_cols": {retail: 3}}
    client.post(
        "/api/catalog/import",
        files={"file": ("bolid.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": str(supplier_id),
            "kind": "material",
            "sheet_mappings": json.dumps([{"name": "Болид", "mapping": mapping}]),
            "use_sheet_as_category": "false",
            "save_mapping": "false",
        },
        headers=admin,
    )
    return retail, supplier_id


def test_search_by_name_case_insensitive(client, db_session):
    admin = make_admin(client, db_session)
    retail, _ = import_bolid(client, admin, db_session)
    resp = client.get("/api/catalog/items?q=сириус", headers=admin)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Сириус"
    assert items[0]["prices"][str(retail)] == "36159.53"


def test_search_by_article(client, db_session):
    admin = make_admin(client, db_session)
    import_bolid(client, admin, db_session)
    items = client.get("/api/catalog/items?q=110-058", headers=admin).json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "С2000-М"


def test_search_pagination_and_total(client, db_session):
    admin = make_admin(client, db_session)
    import_bolid(client, admin, db_session)
    body = client.get("/api/catalog/items?limit=2&offset=0", headers=admin).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_price_history(client, db_session):
    admin = make_admin(client, db_session)
    retail, supplier_id = import_bolid(client, admin, db_session)
    item_id = client.get("/api/catalog/items?q=сириус", headers=admin).json()["items"][0]["id"]
    history = client.get(f"/api/catalog/items/{item_id}/prices", headers=admin).json()
    assert len(history) == 1
    assert history[0]["version"] == 1
    assert history[0]["value"] == "36159.53"


def test_price_lists_by_supplier(client, db_session):
    admin = make_admin(client, db_session)
    _, supplier_id = import_bolid(client, admin, db_session)
    lists = client.get(f"/api/catalog/price-lists?supplier_id={supplier_id}", headers=admin).json()
    assert len(lists) == 1
    assert lists[0]["version"] == 1
    assert lists[0]["filename"] == "bolid.xlsx"


def test_search_wildcards_are_literal(client, db_session):
    from app.catalog.models import CatalogItem, Supplier

    admin = make_admin(client, db_session)
    from sqlalchemy import select
    from app.auth.models import User
    user = db_session.scalars(select(User).where(User.email == "admin@test.ru")).one()
    supplier = Supplier(name="S", org_id=user.org_id)
    db_session.add(supplier)
    db_session.commit()
    db_session.add_all(
        [
            CatalogItem(
                supplier_id=supplier.id, name="Скидка 50%", article="A1", org_id=user.org_id
            ),
            CatalogItem(
                supplier_id=supplier.id, name="Кабель 50м", article="A2", org_id=user.org_id
            ),
        ]
    )
    db_session.commit()
    items = client.get("/api/catalog/items?q=50%25", headers=admin).json()["items"]
    assert [i["name"] for i in items] == ["Скидка 50%"]
