from sqlalchemy import select

from app.auth.models import User
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier
from app.core.security import create_access_token
from app.estimates.models import Estimate, EstimateBranch, EstimateLine, EstimateSection
from app.orgs.models import Organization


def _get_org(db):
    org = db.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db.add(org)
        db.commit()
    return org


def _admin(db):
    org = _get_org(db)
    u = User(email="a@x.ru", name="A", role="org_admin", status="active", org_id=org.id)
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _supplier_with_item(db, name="S", org_id=None):
    sup = Supplier(name=name, org_id=org_id); db.add(sup); db.commit()
    it = CatalogItem(
        supplier_id=sup.id, name="Камера", article="A", unit="шт", kind="material",
        org_id=org_id,
    )
    db.add(it); db.commit()
    pl = PriceList(supplier_id=sup.id, filename="p.xlsx", version=1, org_id=org_id)
    lvl = PriceLevel(name=f"Розница-{name}", sort_order=0, org_id=org_id)
    db.add_all([pl, lvl]); db.commit()
    db.add(ItemPrice(item_id=it.id, price_list_id=pl.id, price_level_id=lvl.id, value=100))
    db.commit()
    return sup, it


def test_clear_catalog_deletes_items_and_unlinks_estimate_lines(client, db_session):
    a = _admin(db_session)
    org = _get_org(db_session)
    sup, it = _supplier_with_item(db_session, org_id=org.id)
    est = Estimate(owner_id=a.id, org_id=org.id, object_name="O"); db_session.add(est); db_session.commit()
    br = EstimateBranch(estimate_id=est.id, name="Базовая"); db_session.add(br); db_session.commit()
    sec = EstimateSection(branch_id=br.id, name="С"); db_session.add(sec); db_session.commit()
    ln = EstimateLine(section_id=sec.id, item_id=it.id, name="Камера", unit="шт", qty=1,
                      material_price=100)
    db_session.add(ln); db_session.commit()

    r = client.request("DELETE", "/api/catalog/items", headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": 1}
    assert db_session.scalars(__import__("sqlalchemy").select(CatalogItem)).all() == []
    assert db_session.scalars(__import__("sqlalchemy").select(ItemPrice)).all() == []
    db_session.refresh(ln)
    assert ln.item_id is None  # строка сметы сохранена, отвязана


def test_clear_catalog_per_supplier(client, db_session):
    a = _admin(db_session)
    org = _get_org(db_session)
    sup1, _ = _supplier_with_item(db_session, "S1", org_id=org.id)
    sup2, _ = _supplier_with_item(db_session, "S2", org_id=org.id)
    r = client.request("DELETE", f"/api/catalog/items?supplier_id={sup1.id}", headers=_hdr(a))
    assert r.json() == {"deleted": 1}
    remaining = db_session.scalars(__import__("sqlalchemy").select(CatalogItem)).all()
    assert {i.supplier_id for i in remaining} == {sup2.id}


def test_clear_catalog_admin_only(client, db_session):
    org = _get_org(db_session)
    e = User(email="e@x.ru", name="E", role="estimator", status="active", org_id=org.id)
    db_session.add(e); db_session.commit()
    assert client.request("DELETE", "/api/catalog/items", headers=_hdr(e)).status_code == 403


def test_force_reextract_resets_characteristics(client, db_session):
    a = _admin(db_session)
    org = _get_org(db_session)
    sup, it = _supplier_with_item(db_session, org_id=org.id)
    it.characteristics = {"Разрешение": "2 Мп"}; db_session.commit()
    r = client.post("/api/catalog/extract-characteristics/start?force=true", headers=_hdr(a))
    assert r.status_code == 200
    db_session.refresh(it)
    assert it.characteristics is None  # сброшено для переизвлечения
