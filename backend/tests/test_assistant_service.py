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


def test_build_context_includes_totals_and_line_sums(db_session):
    from app.estimates import models as em
    est, item = _estimate_with_catalog(db_session)
    sec = em.EstimateSection(branch_id=est.branches[0].id, name="Обор", sort_order=0)
    db_session.add(sec); db_session.commit()
    db_session.add(em.EstimateLine(
        section_id=sec.id, name="Камера", unit="шт", qty=Decimal("2"),
        material_price=Decimal("100"), work_price=Decimal("0"),
    ))
    db_session.commit(); db_session.refresh(est)
    ctx = asvc.build_context(est)
    assert "ИТОГО" in ctx
    assert "сумма 200" in ctx  # 2 × 100
    assert "Обор" in ctx


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


def test_apply_changeset_add_section_and_catalog_line(db_session):
    est, item = _estimate_with_catalog(db_session)
    ops = [
        schemas.AddSection(op="add_section", name="Оборудование"),
        schemas.AddCatalogLine(op="add_catalog_line", section_name="Оборудование",
                               catalog_item_id=item.id, qty=Decimal("3")),
    ]
    asvc.apply_changeset(db_session, est, ops)
    db_session.refresh(est)
    branch = est.branches[0]
    assert len(branch.sections) == 1
    sec = branch.sections[0]
    assert sec.name == "Оборудование"
    assert len(sec.lines) == 1
    assert sec.lines[0].qty == Decimal("3")
    assert sec.lines[0].item_id == item.id


def test_apply_changeset_sort_order_distinct_for_batch_lines(db_session):
    est, item = _estimate_with_catalog(db_session)
    ops = [
        schemas.AddSection(op="add_section", name="Обор"),
        schemas.AddCatalogLine(op="add_catalog_line", section_name="Обор",
                               catalog_item_id=item.id, qty=Decimal("1")),
        schemas.AddCustomLine(op="add_custom_line", section_name="Обор",
                              name="Монтаж", unit="шт", qty=Decimal("1")),
        schemas.AddCatalogLine(op="add_catalog_line", section_name="Обор",
                               catalog_item_id=item.id, qty=Decimal("2")),
    ]
    asvc.apply_changeset(db_session, est, ops)
    db_session.refresh(est)
    sec = est.branches[0].sections[0]
    orders = sorted(ln.sort_order for ln in sec.lines)
    assert orders == [0, 1, 2]  # уникальные, не все 0


def test_apply_changeset_set_qty_and_delete(db_session):
    from app.estimates import models as em
    est, item = _estimate_with_catalog(db_session)
    sec = em.EstimateSection(branch_id=est.branches[0].id, name="С", sort_order=0)
    db_session.add(sec); db_session.commit()
    ln = em.EstimateLine(section_id=sec.id, name="X", unit="шт", qty=Decimal("1"))
    db_session.add(ln); db_session.commit()
    asvc.apply_changeset(db_session, est, [
        schemas.SetQty(op="set_qty", line_id=ln.id, qty=Decimal("5")),
    ])
    db_session.refresh(ln)
    assert ln.qty == Decimal("5")
    asvc.apply_changeset(db_session, est, [
        schemas.DeleteLine(op="delete_line", line_id=ln.id),
    ])
    db_session.refresh(sec)
    assert len(sec.lines) == 0


def test_candidates_include_characteristics(db_session):
    from app.catalog.models import CatalogItem, Supplier
    sup = Supplier(name="P"); db_session.add(sup); db_session.commit()
    it = CatalogItem(supplier_id=sup.id, name="Камера", article="A", unit="шт", kind="material",
                     characteristics={"Разрешение": "2 Мп"})
    db_session.add(it); db_session.commit()
    text, items = asvc._candidates(db_session, ["камера"])
    assert "Разрешение" in text


def test_candidates_per_word_fallback_for_overspecified_query(db_session):
    # многословный запрос с характеристиками не совпадёт по названию целиком,
    # но переспрос по словам должен найти позицию по слову «камера»
    from app.catalog.models import CatalogItem, Supplier
    sup = Supplier(name="P2"); db_session.add(sup); db_session.commit()
    it = CatalogItem(supplier_id=sup.id, name="Видеокамера Optimus IP-E014", article="B",
                     unit="шт", kind="material")
    db_session.add(it); db_session.commit()
    text, items = asvc._candidates(db_session, ["камера уличная 4мп с ик подсветкой"])
    assert any(i.id == it.id for i in items)


def test_apply_changeset_atomic_rollback_on_bad_ref(db_session):
    from app.estimates import models as em
    est, item = _estimate_with_catalog(db_session)
    # add_section валиден, set_qty на чужой line_id (999) — должно откатить ВЕСЬ пакет
    with pytest.raises(Exception):
        asvc.apply_changeset(db_session, est, [
            schemas.AddSection(op="add_section", name="Новый"),
            schemas.SetQty(op="set_qty", line_id=999, qty=Decimal("2")),
        ])
    db_session.rollback()
    db_session.refresh(est)
    assert len(est.branches[0].sections) == 0  # раздел не создан (откат)
