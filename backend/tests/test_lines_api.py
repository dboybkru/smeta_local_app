from decimal import Decimal

from sqlalchemy import select

from app.auth.models import User
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier
from app.core.security import create_access_token
from app.orgs.models import Organization


def _get_org(db_session):
    org = db_session.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db_session.add(org)
        db_session.commit()
    return org


def _user(db_session, role="estimator", email=None):
    org = _get_org(db_session)
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active", org_id=org.id)
    db_session.add(u)
    db_session.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _section(client, u):
    est = client.post("/api/estimates", json={"object_name": "O"}, headers=_hdr(u)).json()
    sec = client.post(
        f"/api/estimates/{est['id']}/sections", json={"name": "S"}, headers=_hdr(u)
    )
    return sec.json()


def _catalog_item(db, kind="material", price="150.00"):
    sup = Supplier(name="P")
    db.add(sup)
    db.commit()
    item = CatalogItem(supplier_id=sup.id, name="Камера 4Мп", article="A", unit="шт", kind=kind)
    db.add(item)
    pl = PriceList(supplier_id=sup.id, filename="p.xlsx", version=1)
    db.add(pl)
    db.commit()
    lvl = PriceLevel(name="Розница", sort_order=0)
    db.add(lvl)
    db.commit()
    db.add(
        ItemPrice(
            item_id=item.id,
            price_list_id=pl.id,
            price_level_id=lvl.id,
            value=Decimal(price),
        )
    )
    db.commit()
    return item


def test_add_line_from_catalog_snapshots_price(client, db_session):
    u = _user(db_session)
    section = _section(client, u)
    item = _catalog_item(db_session, kind="material", price="150.00")
    r = client.post(
        f"/api/sections/{section['id']}/lines",
        json={"item_id": item.id, "qty": "3"},
        headers=_hdr(u),
    )
    assert r.status_code == 201, r.text
    line = r.json()
    assert line["name"] == "Камера 4Мп"
    assert line["material_price"] == "150.00"
    assert line["qty"] == "3.000"


def test_add_freeform_line(client, db_session):
    u = _user(db_session)
    section = _section(client, u)
    r = client.post(
        f"/api/sections/{section['id']}/lines",
        json={"name": "Произвольная работа", "unit": "усл", "qty": "1", "work_price": "2000"},
        headers=_hdr(u),
    )
    assert r.status_code == 201, r.text
    assert r.json()["work_price"] == "2000.00"


def test_freeform_line_with_purchase_shows_margin(client, db_session):
    """Произвольная строка с purchase_price_snapshot даёт ненулевую маржу."""
    u = _user(db_session)
    est_id = client.post("/api/estimates", json={"object_name": "O2"}, headers=_hdr(u)).json()["id"]
    sec2 = client.post(
        f"/api/estimates/{est_id}/sections", json={"name": "S2"}, headers=_hdr(u)
    ).json()
    r = client.post(
        f"/api/sections/{sec2['id']}/lines",
        json={
            "name": "Материал без каталога",
            "unit": "шт",
            "qty": "1",
            "material_price": "100",
            "purchase_price_snapshot": "70",
        },
        headers=_hdr(u),
    )
    assert r.status_code == 201, r.text
    detail = client.get(f"/api/estimates/{est_id}", headers=_hdr(u)).json()
    # margin = продажа - закупка = 100 - 70 = 30
    assert detail["totals"]["margin"] == "30.00", detail["totals"]


def test_patch_line_qty_and_price(client, db_session):
    u = _user(db_session)
    section = _section(client, u)
    lid = client.post(
        f"/api/sections/{section['id']}/lines",
        json={"name": "X", "qty": "1", "material_price": "100"},
        headers=_hdr(u),
    ).json()["id"]
    r = client.patch(
        f"/api/lines/{lid}",
        json={"qty": "5", "material_price": "90"},
        headers=_hdr(u),
    )
    assert r.json()["qty"] == "5.000"
    assert r.json()["material_price"] == "90.00"
    assert client.delete(f"/api/lines/{lid}", headers=_hdr(u)).status_code == 204
