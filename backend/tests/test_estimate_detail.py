from decimal import Decimal

from app.auth.models import User
from app.catalog.models import CatalogItem, ItemPrice, PriceLevel, PriceList, Supplier
from app.core.security import create_access_token


def _user(db_session, role="estimator", email=None):
    u = User(email=email or f"{role}@x.ru", name="U", role=role, status="active")
    db_session.add(u)
    db_session.commit()
    return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _catalog_item(db, price="150.00", purchase="100.00"):
    sup = Supplier(name="P")
    db.add(sup)
    db.commit()
    item = CatalogItem(
        supplier_id=sup.id, name="Камера", article="A", unit="шт", kind="material"
    )
    db.add(item)
    pl = PriceList(supplier_id=sup.id, filename="p.xlsx", version=1)
    db.add(pl)
    db.commit()
    roz = PriceLevel(name="Розница", sort_order=0)
    zak = PriceLevel(name="Закупка", sort_order=1)
    db.add_all([roz, zak])
    db.commit()
    db.add_all([
        ItemPrice(
            item_id=item.id, price_list_id=pl.id, price_level_id=roz.id, value=Decimal(price)
        ),
        ItemPrice(
            item_id=item.id,
            price_list_id=pl.id,
            price_level_id=zak.id,
            value=Decimal(purchase),
        ),
    ])
    db.commit()
    return item


def _build(client, u, db_session):
    item = _catalog_item(db_session)
    est = client.post("/api/estimates", json={"object_name": "O"}, headers=_hdr(u)).json()
    resp = client.post(
        f"/api/estimates/{est['id']}/sections", json={"name": "S"}, headers=_hdr(u)
    )
    sid = resp.json()["id"]
    client.post(
        f"/api/sections/{sid}/lines",
        json={"item_id": item.id, "qty": "2"},
        headers=_hdr(u),
    )
    return est["id"]


def test_detail_has_tree_and_totals(client, db_session):
    u = _user(db_session)
    eid = _build(client, u, db_session)
    r = client.get(f"/api/estimates/{eid}", headers=_hdr(u))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totals"]["subtotal"] == "300.00"
    line = body["branches"][0]["sections"][0]["lines"][0]
    assert line["material_price"] == "150.00"


def test_owner_sees_margin(client, db_session):
    u = _user(db_session)
    eid = _build(client, u, db_session)
    body = client.get(f"/api/estimates/{eid}", headers=_hdr(u)).json()
    assert body["totals"]["margin"] == "100.00"  # 300 sell - 200 purchase
    assert body["branches"][0]["sections"][0]["lines"][0]["purchase_price_snapshot"] == "100.00"


def test_admin_sees_margin_of_others(client, db_session):
    u = _user(db_session, email="owner@x.ru")
    admin = _user(db_session, role="admin", email="adm@x.ru")
    eid = _build(client, u, db_session)
    body = client.get(f"/api/estimates/{eid}", headers=_hdr(admin)).json()
    assert body["totals"]["margin"] == "100.00"


def test_viewer_does_not_see_margin(client, db_session):
    u = _user(db_session, email="owner@x.ru")
    viewer = _user(db_session, role="viewer", email="v@x.ru")
    eid = _build(client, u, db_session)
    body = client.get(f"/api/estimates/{eid}", headers=_hdr(viewer)).json()
    assert body["totals"]["margin"] is None
    assert body["branches"][0]["sections"][0]["lines"][0]["purchase_price_snapshot"] is None


def test_detail_includes_proposal(client, db_session):
    from app.auth.models import User
    from app.core.security import create_access_token
    from app.estimates.models import Estimate

    u = User(email="p@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Объект",
                   proposal={"title": "КП", "advantages": ["a"]})
    db_session.add(est); db_session.commit(); db_session.refresh(est)
    hdr = {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}
    r = client.get(f"/api/estimates/{est.id}", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["proposal"] == {"title": "КП", "advantages": ["a"]}


def test_detail_proposal_null_by_default(client, db_session):
    from app.auth.models import User
    from app.core.security import create_access_token
    from app.estimates.models import Estimate

    u = User(email="p2@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Объект")
    db_session.add(est); db_session.commit(); db_session.refresh(est)
    hdr = {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}
    r = client.get(f"/api/estimates/{est.id}", headers=hdr)
    assert r.json()["proposal"] is None
