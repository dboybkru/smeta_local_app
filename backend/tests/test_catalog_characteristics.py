from app.auth.models import User
from app.catalog.models import CatalogItem, Supplier
from app.core.security import create_access_token
from tests.orghelpers import get_or_create_org as _get_or_create_org


def _admin(db):
    org = _get_or_create_org(db)
    u = User(email="a@x.ru", name="A", role="org_admin", status="active", org_id=org.id)
    db.add(u); db.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _item(db, name="Камера IP 2Мп PoE"):
    org = _get_or_create_org(db)
    sup = Supplier(name="P", org_id=org.id); db.add(sup); db.commit()
    it = CatalogItem(
        supplier_id=sup.id, name=name, article="A", unit="шт", kind="material", org_id=org.id
    )
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


from app.ai import service as ai_service  # noqa: E402
from app.catalog import characteristics as ch  # noqa: E402


def test_extract_batch_sets_characteristics(db_session, monkeypatch):
    it = _item(db_session, name="Камера IP 2Мп PoE")
    org = _get_or_create_org(db_session)
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {
        "items": [{"id": it.id, "characteristics": {"Разрешение": "2 Мп", "Питание": "PoE"}}]
    })
    res = ch.extract_batch(db_session, batch=40, org_id=org.id)
    assert res["processed"] == 1
    assert res["remaining"] == 0
    db_session.refresh(it)
    assert it.characteristics == {"Разрешение": "2 Мп", "Питание": "PoE"}


def test_extract_batch_marks_unanswered_as_empty(db_session, monkeypatch):
    it = _item(db_session, name="Непонятная позиция")
    org = _get_or_create_org(db_session)
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {"items": []})
    res = ch.extract_batch(db_session, batch=40, org_id=org.id)
    assert res["processed"] == 1
    db_session.refresh(it)
    assert it.characteristics == {}  # обработана, но пусто — не зациклит


def test_extract_batch_empty_when_nothing_to_do(db_session, monkeypatch):
    org = _get_or_create_org(db_session)
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: {"items": []})
    res = ch.extract_batch(db_session, batch=40, org_id=org.id)
    assert res == {"processed": 0, "remaining": 0}


def test_extract_uses_raw_as_source(db_session, monkeypatch):
    it = _item(db_session, name="Камера X")
    org = _get_or_create_org(db_session)
    it.characteristics_raw = "2 Мп, объектив 2.8мм, IP67"
    db_session.commit()
    captured = {}
    def fake(db, purpose, messages, **k):
        captured["prompt"] = messages[-1]["content"]
        return {"items": [{"id": it.id, "characteristics": {"Разрешение": "2 Мп"}}]}
    monkeypatch.setattr(ai_service, "call_llm", fake)
    ch.extract_batch(db_session, batch=40, org_id=org.id)
    assert "2.8мм" in captured["prompt"]  # сырьё попало в промпт
    db_session.refresh(it)
    assert it.characteristics == {"Разрешение": "2 Мп"}
