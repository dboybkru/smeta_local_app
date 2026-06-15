from app.auth.models import User
from app.core.security import create_access_token
from app.estimates import models as em
from app.orgs.models import Organization


def _org_user(db, name):
    o = Organization(name=name); db.add(o); db.commit()
    u = User(email=f"a{name}@x.ru", name="A", role="org_admin", status="active", org_id=o.id)
    db.add(u); db.commit(); return o, u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _make_estimate_with_section_and_line(db, org_id, owner_id):
    """Создаёт смету с веткой, разделом и строкой; возвращает (estimate, section, line)."""
    est = em.Estimate(owner_id=owner_id, org_id=org_id, object_name="Объект A")
    branch = em.EstimateBranch(name="Базовая")
    est.branches.append(branch)
    db.add(est)
    db.flush()
    section = em.EstimateSection(branch_id=branch.id, name="Раздел 1", sort_order=0)
    db.add(section)
    db.flush()
    line = em.EstimateLine(
        section_id=section.id, name="Позиция 1", unit="шт", qty=1,
        work_price=100, material_price=0,
    )
    db.add(line)
    db.commit()
    db.refresh(est); db.refresh(section); db.refresh(line)
    return est, section, line


def test_estimate_not_visible_across_orgs(client, db_session):
    oa, ua = _org_user(db_session, "A"); ob, ub = _org_user(db_session, "B")
    est = em.Estimate(owner_id=ua.id, org_id=oa.id, object_name="Секрет A")
    db_session.add(est); db_session.commit()
    assert client.get(f"/api/estimates/{est.id}", headers=_hdr(ub)).status_code == 404
    lst = client.get("/api/estimates", headers=_hdr(ub)).json()
    assert all(e["id"] != est.id for e in (lst if isinstance(lst, list) else lst.get("items", [])))
    assert client.get(f"/api/estimates/{est.id}", headers=_hdr(ua)).status_code == 200


def test_client_isolated_across_orgs(client, db_session):
    oa, ua = _org_user(db_session, "CA"); ob, ub = _org_user(db_session, "CB")
    db_session.add(em.Client(name="Клиент A", org_id=oa.id)); db_session.commit()
    lst = client.get("/api/clients", headers=_hdr(ub)).json()
    assert all(c["name"] != "Клиент A" for c in lst)


def test_section_not_accessible_across_orgs(client, db_session):
    """org_admin из org B не может читать/изменять раздел org A через PATCH /sections/{id}."""
    oa, ua = _org_user(db_session, "SA"); ob, ub = _org_user(db_session, "SB")
    _est, section, _line = _make_estimate_with_section_and_line(db_session, oa.id, ua.id)

    # org B org_admin пытается изменить раздел org A — должен получить 404
    r = client.patch(
        f"/api/sections/{section.id}",
        json={"name": "Взлом"},
        headers=_hdr(ub),
    )
    assert r.status_code == 404, f"Ожидался 404, получен {r.status_code}: {r.text}"

    # org B org_admin пытается удалить раздел org A — должен получить 404
    r = client.delete(f"/api/sections/{section.id}", headers=_hdr(ub))
    assert r.status_code == 404, f"Ожидался 404, получен {r.status_code}: {r.text}"

    # org A org_admin имеет доступ к своему разделу
    r = client.patch(
        f"/api/sections/{section.id}",
        json={"name": "Свой раздел"},
        headers=_hdr(ua),
    )
    assert r.status_code == 200, f"org A должен иметь доступ, получен {r.status_code}: {r.text}"


def test_line_not_accessible_across_orgs(client, db_session):
    """org_admin из org B не может изменять строку org A через PATCH /lines/{id}."""
    oa, ua = _org_user(db_session, "LA"); ob, ub = _org_user(db_session, "LB")
    _est, _section, line = _make_estimate_with_section_and_line(db_session, oa.id, ua.id)

    # org B org_admin пытается изменить строку org A — должен получить 404
    r = client.patch(
        f"/api/lines/{line.id}",
        json={"name": "Взлом"},
        headers=_hdr(ub),
    )
    assert r.status_code == 404, f"Ожидался 404, получен {r.status_code}: {r.text}"

    # org B org_admin пытается удалить строку org A — должен получить 404
    r = client.delete(f"/api/lines/{line.id}", headers=_hdr(ub))
    assert r.status_code == 404, f"Ожидался 404, получен {r.status_code}: {r.text}"

    # org A org_admin имеет доступ к своей строке
    r = client.patch(
        f"/api/lines/{line.id}",
        json={"name": "Своя позиция"},
        headers=_hdr(ua),
    )
    assert r.status_code == 200, f"org A должен иметь доступ, получен {r.status_code}: {r.text}"


def test_client_id_cross_org_leak_on_create(client, db_session):
    """org B не может создать смету с client_id, принадлежащим org A (межорг-утечка реквизитов)."""
    oa, ua = _org_user(db_session, "CIA")
    ob, ub = _org_user(db_session, "CIB")

    # Создаём клиента в org A через API
    r = client.post(
        "/api/clients",
        json={"name": "Клиент Орг А"},
        headers=_hdr(ua),
    )
    assert r.status_code == 201, r.text
    client_a_id = r.json()["id"]

    # org B пытается создать смету с client_id = клиент org A — должен получить 404
    r = client.post(
        "/api/estimates",
        json={"object_name": "Объект B", "client_id": client_a_id},
        headers=_hdr(ub),
    )
    assert r.status_code == 404, (
        f"Ожидался 404 при использовании чужого client_id на create, получен {r.status_code}: {r.text}"
    )


def test_client_id_cross_org_leak_on_patch(client, db_session):
    """org B не может PATCH сметы с client_id org A; но может использовать свой client_id."""
    oa, ua = _org_user(db_session, "PIA")
    ob, ub = _org_user(db_session, "PIB")

    # Создаём клиента в org A
    r = client.post(
        "/api/clients",
        json={"name": "Клиент Орг А (patch)"},
        headers=_hdr(ua),
    )
    assert r.status_code == 201, r.text
    client_a_id = r.json()["id"]

    # org B создаёт смету БЕЗ client_id — должно пройти успешно
    r = client.post(
        "/api/estimates",
        json={"object_name": "Объект B без клиента"},
        headers=_hdr(ub),
    )
    assert r.status_code == 201, (
        f"Ожидался 201 при создании сметы без client_id, получен {r.status_code}: {r.text}"
    )
    est_b_id = r.json()["id"]

    # org B пытается PATCH смету с client_id = клиент org A — должен получить 404
    r = client.patch(
        f"/api/estimates/{est_b_id}",
        json={"client_id": client_a_id},
        headers=_hdr(ub),
    )
    assert r.status_code == 404, (
        f"Ожидался 404 при PATCH с чужим client_id, получен {r.status_code}: {r.text}"
    )

    # Позитивный контроль: org B создаёт своего клиента и PATCH со своим client_id — успех
    r = client.post(
        "/api/clients",
        json={"name": "Клиент Орг B"},
        headers=_hdr(ub),
    )
    assert r.status_code == 201, r.text
    client_b_id = r.json()["id"]

    r = client.patch(
        f"/api/estimates/{est_b_id}",
        json={"client_id": client_b_id},
        headers=_hdr(ub),
    )
    assert r.status_code == 200, (
        f"org B должна иметь возможность использовать своего клиента, получен {r.status_code}: {r.text}"
    )
