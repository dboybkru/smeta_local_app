import json

from tests.catalog_files import make_bolid_xlsx
from tests.test_price_levels import make_admin


def import_bolid(client, admin):
    retail = client.post("/api/price-levels", json={"name": "Розница"}, headers=admin).json()["id"]
    supplier_id = client.post("/api/suppliers", json={"name": "Bolid"}, headers=admin).json()["id"]
    mapping = {"name_col": 0, "article_col": 2, "price_cols": {retail: 3}}
    client.post(
        "/api/catalog/import",
        files={"file": ("bolid.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": str(supplier_id),
            "kind": "material",
            "sheets": json.dumps(["Болид"]),
            "mapping": json.dumps(mapping),
            "use_sheet_as_category": "false",
            "save_mapping": "false",
        },
        headers=admin,
    )
    return retail, supplier_id


def test_search_by_name_case_insensitive(client):
    admin = make_admin(client)
    retail, _ = import_bolid(client, admin)
    resp = client.get("/api/catalog/items?q=сириус", headers=admin)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Сириус"
    assert items[0]["prices"][str(retail)] == "36159.53"


def test_search_by_article(client):
    admin = make_admin(client)
    import_bolid(client, admin)
    items = client.get("/api/catalog/items?q=110-058", headers=admin).json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "С2000-М"


def test_search_pagination_and_total(client):
    admin = make_admin(client)
    import_bolid(client, admin)
    body = client.get("/api/catalog/items?limit=2&offset=0", headers=admin).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_price_history(client):
    admin = make_admin(client)
    retail, supplier_id = import_bolid(client, admin)
    item_id = client.get("/api/catalog/items?q=сириус", headers=admin).json()["items"][0]["id"]
    history = client.get(f"/api/catalog/items/{item_id}/prices", headers=admin).json()
    assert len(history) == 1
    assert history[0]["version"] == 1
    assert history[0]["value"] == "36159.53"


def test_price_lists_by_supplier(client):
    admin = make_admin(client)
    _, supplier_id = import_bolid(client, admin)
    lists = client.get(f"/api/catalog/price-lists?supplier_id={supplier_id}", headers=admin).json()
    assert len(lists) == 1
    assert lists[0]["version"] == 1
    assert lists[0]["filename"] == "bolid.xlsx"
