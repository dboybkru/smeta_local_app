"""Org-isolation tests for the catalog domain (Task 5)."""
import json
from decimal import Decimal

import pytest

from app.auth.models import User
from app.catalog.models import CatalogItem, PriceLevel, Supplier
from app.core.security import create_access_token
from app.orgs.models import Organization


def _org_admin(db, name):
    o = Organization(name=name)
    db.add(o)
    db.commit()
    u = User(email=f"c{name}@x.ru", name="A", role="org_admin", status="active", org_id=o.id)
    db.add(u)
    db.commit()
    return o, u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_catalog_items_isolated(client, db_session):
    oa, ua = _org_admin(db_session, "KA")
    ob, ub = _org_admin(db_session, "KB")
    sup = Supplier(name="S", org_id=oa.id)
    db_session.add(sup)
    db_session.commit()
    db_session.add(
        CatalogItem(
            supplier_id=sup.id,
            org_id=oa.id,
            name="Камера A",
            kind="material",
        )
    )
    db_session.commit()
    items = client.get("/api/catalog/items", headers=_hdr(ub)).json()["items"]
    assert all(i["name"] != "Камера A" for i in items)
    items_a = client.get("/api/catalog/items", headers=_hdr(ua)).json()["items"]
    assert any(i["name"] == "Камера A" for i in items_a)


def test_same_price_level_name_allowed_in_two_orgs(db_session):
    oa, _ = _org_admin(db_session, "PA")
    ob, _ = _org_admin(db_session, "PB")
    db_session.add(PriceLevel(name="Розница", org_id=oa.id))
    db_session.add(PriceLevel(name="Розница", org_id=ob.id))
    db_session.commit()  # must NOT raise (per-org unique)


def test_same_supplier_name_allowed_in_two_orgs(db_session):
    oa, _ = _org_admin(db_session, "SA")
    ob, _ = _org_admin(db_session, "SB")
    db_session.add(Supplier(name="Bolid", org_id=oa.id))
    db_session.add(Supplier(name="Bolid", org_id=ob.id))
    db_session.commit()  # must NOT raise (per-org unique)


def test_suppliers_isolated(client, db_session):
    oa, ua = _org_admin(db_session, "SupA")
    ob, ub = _org_admin(db_session, "SupB")
    r = client.post("/api/suppliers", json={"name": "Тайный поставщик"}, headers=_hdr(ua))
    assert r.status_code == 201, r.text
    # org B should not see org A's supplier
    suppliers_b = client.get("/api/suppliers", headers=_hdr(ub)).json()
    assert all(s["name"] != "Тайный поставщик" for s in suppliers_b)


def test_price_levels_isolated(client, db_session):
    oa, ua = _org_admin(db_session, "PLA")
    ob, ub = _org_admin(db_session, "PLB")
    r = client.post("/api/price-levels", json={"name": "Секретный уровень"}, headers=_hdr(ua))
    assert r.status_code == 201, r.text
    levels_b = client.get("/api/price-levels", headers=_hdr(ub)).json()
    assert all(lvl["name"] != "Секретный уровень" for lvl in levels_b)


def test_duplicate_price_level_same_org_409(client, db_session):
    oa, ua = _org_admin(db_session, "DPL")
    client.post("/api/price-levels", json={"name": "Опт"}, headers=_hdr(ua))
    r = client.post("/api/price-levels", json={"name": "Опт"}, headers=_hdr(ua))
    assert r.status_code == 409


def test_clear_catalog_scoped_to_org(client, db_session):
    """clear_catalog must not delete another org's items."""
    oa, ua = _org_admin(db_session, "CCA")
    ob, ub = _org_admin(db_session, "CCB")
    sup_a = Supplier(name="SupA", org_id=oa.id)
    sup_b = Supplier(name="SupB", org_id=ob.id)
    db_session.add_all([sup_a, sup_b])
    db_session.commit()
    db_session.add(CatalogItem(supplier_id=sup_a.id, org_id=oa.id, name="Item A", kind="material"))
    db_session.add(CatalogItem(supplier_id=sup_b.id, org_id=ob.id, name="Item B", kind="material"))
    db_session.commit()
    # org A clears its own catalog
    r = client.request("DELETE", "/api/catalog/items", headers=_hdr(ua))
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == 1
    # org B item should still be there
    items_b = client.get("/api/catalog/items", headers=_hdr(ub)).json()["items"]
    assert any(i["name"] == "Item B" for i in items_b)


def test_client_cross_org_price_level_rejected(client, db_session):
    """Creating a client with another org's price_level_id must 404."""
    from app.catalog.models import PriceLevel as PL

    oa, ua = _org_admin(db_session, "CPL_A")
    ob, ub = _org_admin(db_session, "CPL_B")
    level_a = PL(name="Розница", org_id=oa.id)
    db_session.add(level_a)
    db_session.commit()
    # org B tries to create a client referencing org A's price level
    r = client.post(
        "/api/clients",
        json={"name": "Клиент", "default_price_level_id": level_a.id},
        headers=_hdr(ub),
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_update_client_cross_org_price_level_rejected(client, db_session):
    """PATCH-ing a client with another org's default_price_level_id must 404."""
    from app.catalog.models import PriceLevel as PL

    oa, ua = _org_admin(db_session, "UPL_A")
    ob, ub = _org_admin(db_session, "UPL_B")
    level_a = PL(name="Розница", org_id=oa.id)
    db_session.add(level_a)
    db_session.commit()
    # org B creates its own client first
    r = client.post("/api/clients", json={"name": "Клиент Б"}, headers=_hdr(ub))
    assert r.status_code == 201, r.text
    client_b_id = r.json()["id"]
    # org B tries to patch the client referencing org A's price level
    r = client.patch(
        f"/api/clients/{client_b_id}",
        json={"default_price_level_id": level_a.id},
        headers=_hdr(ub),
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_add_line_cross_org_item_rejected(client, db_session):
    """POST add-line with another org's catalog item_id must return 404."""
    from app.catalog.models import CatalogItem as CI, Supplier as Sup

    # org A has a supplier and catalog item
    oa, ua = _org_admin(db_session, "ALI_A")
    ob, ub = _org_admin(db_session, "ALI_B")
    sup_a = Sup(name="SupA", org_id=oa.id)
    db_session.add(sup_a)
    db_session.commit()
    item_a = CI(supplier_id=sup_a.id, org_id=oa.id, name="Секретная камера", kind="material")
    db_session.add(item_a)
    db_session.commit()

    # org B creates an estimate and section
    est_b = client.post("/api/estimates", json={"object_name": "Объект Б"}, headers=_hdr(ub)).json()
    sec_b = client.post(
        f"/api/estimates/{est_b['id']}/sections", json={"name": "Раздел Б"}, headers=_hdr(ub)
    ).json()

    # org B tries to add a line referencing org A's item → must be 404
    r = client.post(
        f"/api/sections/{sec_b['id']}/lines",
        json={"item_id": item_a.id, "qty": "1"},
        headers=_hdr(ub),
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_import_cross_org_price_level_rejected(client, db_session):
    """Импорт с price_cols, ссылающимся на чужой PriceLevel, должен вернуть 422."""
    from tests.catalog_files import make_bolid_xlsx

    oa, ua = _org_admin(db_session, "IMP_A")
    ob, ub = _org_admin(db_session, "IMP_B")

    # Создаём PriceLevel у org A
    level_a_resp = client.post(
        "/api/price-levels", json={"name": "Розница"}, headers=_hdr(ua)
    )
    assert level_a_resp.status_code == 201, level_a_resp.text
    level_a_id = level_a_resp.json()["id"]

    # Создаём поставщика у org B
    sup_b_resp = client.post("/api/suppliers", json={"name": "ПоставщикБ"}, headers=_hdr(ub))
    assert sup_b_resp.status_code == 201, sup_b_resp.text
    sup_b_id = sup_b_resp.json()["id"]

    # Org B пытается импортировать с маппингом, ссылающимся на level_id org A
    mapping = {"name_col": 0, "article_col": 2, "header_row": 0, "price_cols": {level_a_id: 3}}
    r = client.post(
        "/api/catalog/import",
        files={"file": ("bolid.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": str(sup_b_id),
            "kind": "material",
            "sheet_mappings": json.dumps([{"name": "Болид", "mapping": mapping}]),
            "use_sheet_as_category": "false",
            "save_mapping": "false",
        },
        headers=_hdr(ub),
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
    assert "уровень цены" in r.json()["detail"].lower()

    # Убеждаемся, что ничего не импортировалось
    items_b = client.get("/api/catalog/items", headers=_hdr(ub)).json()["items"]
    assert len(items_b) == 0, "Импорт не должен был создать позиции"


def test_import_own_price_level_succeeds(client, db_session):
    """Импорт со своим PriceLevel должен проходить успешно (регрессия)."""
    from tests.catalog_files import make_bolid_xlsx

    oa, ua = _org_admin(db_session, "IMP_OWN")

    level_resp = client.post(
        "/api/price-levels", json={"name": "Розница"}, headers=_hdr(ua)
    )
    assert level_resp.status_code == 201, level_resp.text
    level_id = level_resp.json()["id"]

    sup_resp = client.post("/api/suppliers", json={"name": "Болид"}, headers=_hdr(ua))
    assert sup_resp.status_code == 201, sup_resp.text
    sup_id = sup_resp.json()["id"]

    mapping = {"name_col": 0, "article_col": 2, "header_row": 0, "price_cols": {level_id: 3}}
    r = client.post(
        "/api/catalog/import",
        files={"file": ("bolid.xlsx", make_bolid_xlsx())},
        data={
            "supplier_id": str(sup_id),
            "kind": "material",
            "sheet_mappings": json.dumps([{"name": "Болид", "mapping": mapping}]),
            "use_sheet_as_category": "false",
            "save_mapping": "false",
        },
        headers=_hdr(ua),
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["items_created"] == 3
