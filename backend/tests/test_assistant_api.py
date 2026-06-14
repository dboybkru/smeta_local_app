from decimal import Decimal

from app.ai import service as ai_service
from app.auth.models import User
from app.catalog.models import CatalogItem, Supplier
from app.core.security import create_access_token
from app.estimates import models as em


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _setup(db_session, role="estimator"):
    u = User(email=f"{role}@x.ru", name="U", role=role, status="active")
    db_session.add(u); db_session.commit()
    sup = Supplier(name="P"); db_session.add(sup); db_session.commit()
    item = CatalogItem(supplier_id=sup.id, name="Камера", article="A", unit="шт", kind="material")
    db_session.add(item); db_session.commit()
    est = em.Estimate(owner_id=u.id, object_name="O")
    db_session.add(est); db_session.commit()
    db_session.add(em.EstimateBranch(estimate_id=est.id, name="Базовая")); db_session.commit()
    db_session.refresh(est)
    return u, est, item


def test_chat_returns_reply_and_operations(client, db_session, monkeypatch):
    u, est, item = _setup(db_session)
    calls = [
        {"queries": ["камера"]},
        {"reply": "ок", "operations": [{"op": "add_section", "name": "Обор"}]},
    ]
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: calls.pop(0))
    r = client.post(f"/api/estimates/{est.id}/assistant/chat", headers=_hdr(u),
                    json={"messages": [{"role": "user", "content": "добавь раздел"}]})
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "ок"
    assert r.json()["operations"][0]["op"] == "add_section"


def test_apply_mutates_and_returns_detail(client, db_session):
    u, est, item = _setup(db_session)
    r = client.post(f"/api/estimates/{est.id}/assistant/apply", headers=_hdr(u),
                    json={"operations": [
                        {"op": "add_section", "name": "Оборудование"},
                        {"op": "add_catalog_line", "section_name": "Оборудование",
                         "catalog_item_id": item.id, "qty": "2"},
                    ]})
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["branches"][0]["sections"][0]["name"] == "Оборудование"
    assert detail["branches"][0]["sections"][0]["lines"][0]["qty"] == "2.000"


def test_viewer_cannot_use_assistant(client, db_session):
    u, est, item = _setup(db_session)
    viewer = User(email="v@x.ru", name="V", role="viewer", status="active")
    db_session.add(viewer); db_session.commit()
    r = client.post(f"/api/estimates/{est.id}/assistant/apply", headers=_hdr(viewer),
                    json={"operations": []})
    assert r.status_code == 403


def test_chat_503_when_ai_not_configured(client, db_session, monkeypatch):
    from app.ai.errors import AINotConfigured
    u, est, item = _setup(db_session)
    def boom(*a, **k):
        raise AINotConfigured("не настроен")
    monkeypatch.setattr(ai_service, "call_llm", boom)
    r = client.post(f"/api/estimates/{est.id}/assistant/chat", headers=_hdr(u),
                    json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503
