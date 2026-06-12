import json

from tests.catalog_files import make_bolid_xlsx, make_optimus_xlsx
from tests.test_price_levels import make_admin


def create_level(client, admin, name):
    return client.post("/api/price-levels", json={"name": name}, headers=admin).json()["id"]


def create_supplier(client, admin, name="Bolid"):
    return client.post("/api/suppliers", json={"name": name}, headers=admin).json()["id"]


def test_inspect_returns_sheets_and_columns(client):
    admin = make_admin(client)
    resp = client.post(
        "/api/catalog/inspect",
        files={"file": ("optimus.xlsx", make_optimus_xlsx())},
        headers=admin,
    )
    assert resp.status_code == 200
    sheets = resp.json()["sheets"]
    assert [s["name"] for s in sheets] == ["IP камеры", "Сетевое оборудование"]
    cam = sheets[0]
    assert cam["header_row"] == 2
    assert cam["columns"][0]["header"] == "Модель"
    assert cam["columns"][2]["samples"] == ["3210.5", "5283"]


def test_import_bolid_end_to_end(client):
    admin = make_admin(client)
    retail = create_level(client, admin, "Розница")
    opt = create_level(client, admin, "Опт")
    supplier_id = create_supplier(client, admin)
    mapping = {"name_col": 0, "article_col": 2, "price_cols": {retail: 3, opt: 4}}
    resp = client.post(
        "/api/catalog/import",
        files={"file": ("bolid.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": str(supplier_id),
            "kind": "material",
            "sheets": json.dumps(["Болид"]),
            "mapping": json.dumps(mapping),
            "use_sheet_as_category": "false",
            "save_mapping": "true",
        },
        headers=admin,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 1
    assert body["items_created"] == 3
    assert body["prices_written"] == 6
    # шаблон маппинга сохранился у поставщика
    suppliers = client.get("/api/suppliers", headers=admin).json()
    assert suppliers[0]["column_mapping_template"]["name_col"] == 0


def test_import_optimus_sheet_as_category(client):
    admin = make_admin(client)
    partner = create_level(client, admin, "Партнёр")
    supplier_id = create_supplier(client, admin, "Optimus")
    mapping = {"name_col": 1, "article_col": 0, "price_cols": {partner: 2}}
    resp = client.post(
        "/api/catalog/import",
        files={"file": ("optimus.xlsx", make_optimus_xlsx())},
        data={
            "supplier_id": str(supplier_id),
            "kind": "material",
            "sheets": json.dumps(["IP камеры", "Сетевое оборудование"]),
            "mapping": json.dumps(mapping),
            "use_sheet_as_category": "true",
            "save_mapping": "false",
        },
        headers=admin,
    )
    assert resp.status_code == 200
    assert resp.json()["items_created"] == 3


def test_import_unknown_supplier_404(client):
    admin = make_admin(client)
    resp = client.post(
        "/api/catalog/import",
        files={"file": ("b.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": "999",
            "kind": "material",
            "sheets": json.dumps(["Болид"]),
            "mapping": json.dumps({"name_col": 0, "price_cols": {}}),
            "use_sheet_as_category": "false",
            "save_mapping": "false",
        },
        headers=admin,
    )
    assert resp.status_code == 404


def test_inspect_bad_extension_415(client):
    admin = make_admin(client)
    resp = client.post(
        "/api/catalog/inspect", files={"file": ("doc.pdf", b"%PDF")}, headers=admin
    )
    assert resp.status_code == 415


def test_oversized_upload_413(client):
    admin = make_admin(client)
    big = b"x" * (25 * 1024 * 1024 + 1)
    resp = client.post(
        "/api/catalog/inspect", files={"file": ("big.xlsx", big)}, headers=admin
    )
    assert resp.status_code == 413
