from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.assistant import schemas


def test_operation_union_discriminates_by_op():
    adapter = TypeAdapter(schemas.Operation)
    add = adapter.validate_python({"op": "add_section", "name": "Оборудование"})
    assert isinstance(add, schemas.AddSection)
    line = adapter.validate_python(
        {"op": "add_catalog_line", "section_name": "Оборудование", "catalog_item_id": 5, "qty": "2"}
    )
    assert isinstance(line, schemas.AddCatalogLine)
    assert line.qty == Decimal("2")
    with pytest.raises(ValidationError):
        adapter.validate_python({"op": "nope"})


from app.assistant import service as asvc  # noqa: E402
from app.ai import service as ai_service  # noqa: E402


def _estimate_with_catalog(db_session):
    from app.auth.models import User
    from app.catalog.models import CatalogItem, Supplier
    from app.estimates import models as em
    u = User(email="a@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    sup = Supplier(name="P"); db_session.add(sup); db_session.commit()
    item = CatalogItem(supplier_id=sup.id, name="Камера IP", article="A", unit="шт", kind="material")
    db_session.add(item); db_session.commit()
    est = em.Estimate(owner_id=u.id, object_name="Склад")
    db_session.add(est); db_session.commit()
    br = em.EstimateBranch(estimate_id=est.id, name="Базовая")
    db_session.add(br); db_session.commit()
    db_session.refresh(est)
    return est, item


def test_run_assistant_two_step(db_session, monkeypatch):
    est, item = _estimate_with_catalog(db_session)
    calls = [
        {"queries": ["камера"]},  # шаг 1
        {"reply": "Добавил камеру.", "operations": [
            {"op": "add_section", "name": "Оборудование"},
            {"op": "add_catalog_line", "section_name": "Оборудование",
             "catalog_item_id": item.id, "qty": "2"},
        ]},  # шаг 2
    ]
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: calls.pop(0))
    out = asvc.run_assistant(db_session, est, [schemas.ChatMessage(role="user", content="добавь камеру")])
    assert out.reply == "Добавил камеру."
    assert len(out.operations) == 2
    assert isinstance(out.operations[1], schemas.AddCatalogLine)


def test_run_assistant_skips_invalid_ops(db_session, monkeypatch):
    est, _ = _estimate_with_catalog(db_session)
    calls = [
        {"queries": []},
        {"reply": "ок", "operations": [
            {"op": "add_section", "name": "Раздел"},
            {"op": "garbage"},  # невалидная — пропускается
        ]},
    ]
    monkeypatch.setattr(ai_service, "call_llm", lambda *a, **k: calls.pop(0))
    out = asvc.run_assistant(db_session, est, [schemas.ChatMessage(role="user", content="hi")])
    assert len(out.operations) == 1
