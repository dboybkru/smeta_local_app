from app.auth.models import User
from app.catalog.models import CatalogItem, Supplier
from app.core.security import create_access_token


def _admin(db):
    u = User(email="a@x.ru", name="A", role="admin", status="active")
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _item(db, name="Камера IP 2Мп PoE"):
    sup = Supplier(name="P"); db.add(sup); db.commit()
    it = CatalogItem(supplier_id=sup.id, name=name, article="A", unit="шт", kind="material")
    db.add(it); db.commit(); db.refresh(it)
    return it


def test_item_characteristics_default_none_and_settable(db_session):
    it = _item(db_session)
    assert it.characteristics is None
    it.characteristics = {"Разрешение": "2 Мп", "Питание": "PoE"}
    db_session.commit(); db_session.refresh(it)
    assert it.characteristics["Питание"] == "PoE"


def test_list_items_returns_characteristics(client, db_session):
    a = _admin(db_session)
    it = _item(db_session)
    it.characteristics = {"Разрешение": "2 Мп"}
    db_session.commit()
    r = client.get("/api/catalog/items", headers=_hdr(a))
    assert r.status_code == 200, r.text
    item = next(x for x in r.json()["items"] if x["id"] == it.id)
    assert item["characteristics"] == {"Разрешение": "2 Мп"}
