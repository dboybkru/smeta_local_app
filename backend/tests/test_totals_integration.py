from decimal import Decimal

from sqlalchemy import select

from app.auth.models import User
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier
from app.core.security import create_access_token
from app.orgs.models import Organization


def _get_org(db):
    org = db.scalars(select(Organization).limit(1)).first()
    if org is None:
        org = Organization(name="TestOrg")
        db.add(org)
        db.commit()
    return org


def _user(db, role="estimator", email=None):
    org = _get_org(db)
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active", org_id=org.id)
    db.add(u)
    db.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _item(db, name, kind, roz, zak):
    sup = Supplier(name=f"S-{name}")
    db.add(sup)
    db.commit()
    it = CatalogItem(supplier_id=sup.id, name=name, article=name, unit="шт", kind=kind)
    db.add(it)
    pl = PriceList(supplier_id=sup.id, filename="p", version=1)
    db.add(pl)
    db.commit()
    levels = {lvl.name: lvl for lvl in db.query(PriceLevel).all()}
    db.add(
        ItemPrice(
            item_id=it.id,
            price_list_id=pl.id,
            price_level_id=levels["Розница"].id,
            value=Decimal(roz),
        )
    )
    db.add(
        ItemPrice(
            item_id=it.id,
            price_list_id=pl.id,
            price_level_id=levels["Закупка"].id,
            value=Decimal(zak),
        )
    )
    db.commit()
    return it


def _setup_levels(db):
    db.add_all([PriceLevel(name="Розница", sort_order=0), PriceLevel(name="Закупка", sort_order=1)])
    db.commit()


def test_full_estimate_two_sections_markup_and_vat(client, db_session):
    _setup_levels(db_session)
    cam = _item(db_session, "Камера", "material", "10000", "7000")
    mount = _item(db_session, "Монтаж", "work", "2000", "0")
    u = _user(db_session)

    eid = client.post(
        "/api/estimates",
        json={"object_name": "Объект", "vat_enabled": True, "vat_rate": "20"},
        headers=_hdr(u),
    ).json()["id"]
    # Раздел 1: оборудование, наценка 10%
    s1 = client.post(
        f"/api/estimates/{eid}/sections",
        json={"name": "Видеонаблюдение", "markup_percent": "10"},
        headers=_hdr(u),
    ).json()["id"]
    client.post(f"/api/sections/{s1}/lines", json={"item_id": cam.id, "qty": "4"}, headers=_hdr(u))
    # Раздел 2: работы, без наценки
    s2 = client.post(
        f"/api/estimates/{eid}/sections",
        json={"name": "Монтажные работы", "markup_percent": "0"},
        headers=_hdr(u),
    ).json()["id"]
    client.post(
        f"/api/sections/{s2}/lines", json={"item_id": mount.id, "qty": "4"}, headers=_hdr(u)
    )

    t = client.get(f"/api/estimates/{eid}", headers=_hdr(u)).json()["totals"]
    # Раздел1: материалы 4*10000=40000, +10% -> 44000
    # Раздел2: работы 4*2000=8000, +0% -> 8000
    # subtotal = 44000 + 8000 = 52000
    assert t["subtotal"] == "52000.00"
    # НДС 20% -> 10400; total 62400
    assert t["vat"] == "10400.00"
    assert t["total"] == "62400.00"
    # закупка: р1 4*7000=28000, р2 4*0=0 -> 28000; маржа 52000-28000=24000
    assert t["purchase"] == "28000.00"
    assert t["margin"] == "24000.00"
    # аккумуляция по двум разделам
    assert len(t["sections"]) == 2
    assert t["sections"][0]["total"] == "44000.00"
    assert t["sections"][1]["total"] == "8000.00"


def test_viewer_sees_no_purchase_anywhere(client, db_session):
    _setup_levels(db_session)
    cam = _item(db_session, "Камера", "material", "10000", "7000")
    owner = _user(db_session, email="owner@x.ru")
    viewer = _user(db_session, role="viewer", email="v@x.ru")

    eid = client.post("/api/estimates", json={"object_name": "O"}, headers=_hdr(owner)).json()["id"]
    s1 = client.post(
        f"/api/estimates/{eid}/sections", json={"name": "S"}, headers=_hdr(owner)
    ).json()["id"]
    client.post(
        f"/api/sections/{s1}/lines",
        json={"item_id": cam.id, "qty": "1"},
        headers=_hdr(owner),
    )

    body = client.get(f"/api/estimates/{eid}", headers=_hdr(viewer)).json()
    # закупка и маржа скрыты на ВСЕХ уровнях
    assert body["totals"]["purchase"] is None
    assert body["totals"]["margin"] is None
    assert body["totals"]["sections"][0]["purchase"] is None
    assert body["totals"]["sections"][0]["margin"] is None
    assert body["branches"][0]["sections"][0]["lines"][0]["purchase_price_snapshot"] is None
    # но продажные числа viewer видит
    assert body["totals"]["subtotal"] == "10000.00"


def test_empty_section_does_not_break_totals(client, db_session):
    _setup_levels(db_session)
    u = _user(db_session)
    eid = client.post("/api/estimates", json={"object_name": "O"}, headers=_hdr(u)).json()["id"]
    client.post(f"/api/estimates/{eid}/sections", json={"name": "Пустой"}, headers=_hdr(u))
    t = client.get(f"/api/estimates/{eid}", headers=_hdr(u)).json()["totals"]
    assert t["subtotal"] == "0.00"
    assert t["sections"][0]["total"] == "0.00"
