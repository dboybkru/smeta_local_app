from sqlalchemy import select

from app.auth.models import User
from app.core.security import create_access_token
from app.orgs.models import Organization


def make_admin(client, db):
    """Register+login the first (superuser) user, also creates an Organization and
    assigns org_id to the user so current_org() works in catalog endpoints."""
    resp = client.post(
        "/api/auth/register",
        json={"email": "admin@test.ru", "password": "secret123", "name": "А"},
    )
    assert resp.status_code == 201
    user = db.scalars(select(User).where(User.email == "admin@test.ru")).one()
    if user.org_id is None:
        org = Organization(name="TestAdminOrg")
        db.add(org)
        db.commit()
        user.org_id = org.id
        db.commit()
    resp = client.post(
        "/api/auth/login", json={"email": "admin@test.ru", "password": "secret123"}
    )
    assert resp.status_code == 200
    user_data = resp.json()
    # Очищаем cookie-jar чтобы Bearer-заголовки не перекрывались cookie от login
    client.cookies.clear()
    return {"Authorization": f"Bearer {create_access_token(user_data['id'], user_data['role'])}"}


def test_admin_creates_and_lists_levels(client, db_session):
    admin = make_admin(client, db_session)
    resp = client.post(
        "/api/price-levels", json={"name": "Закупка", "sort_order": 1}, headers=admin
    )
    assert resp.status_code == 201
    client.post("/api/price-levels", json={"name": "Розница", "sort_order": 2}, headers=admin)
    resp = client.get("/api/price-levels", headers=admin)
    assert [lvl["name"] for lvl in resp.json()] == ["Закупка", "Розница"]


def test_duplicate_level_name_409(client, db_session):
    admin = make_admin(client, db_session)
    client.post("/api/price-levels", json={"name": "Опт"}, headers=admin)
    resp = client.post("/api/price-levels", json={"name": "Опт"}, headers=admin)
    assert resp.status_code == 409


def test_rename_level(client, db_session):
    admin = make_admin(client, db_session)
    lvl = client.post("/api/price-levels", json={"name": "Опт"}, headers=admin).json()
    resp = client.patch(
        f"/api/price-levels/{lvl['id']}", json={"name": "Опт 2026"}, headers=admin
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Опт 2026"


def test_delete_level(client, db_session):
    admin = make_admin(client, db_session)
    lvl = client.post("/api/price-levels", json={"name": "Врем"}, headers=admin).json()
    assert client.delete(f"/api/price-levels/{lvl['id']}", headers=admin).status_code == 204
    assert client.get("/api/price-levels", headers=admin).json() == []


def test_rename_to_existing_name_409(client, db_session):
    admin = make_admin(client, db_session)
    client.post("/api/price-levels", json={"name": "Закупка"}, headers=admin)
    lvl = client.post("/api/price-levels", json={"name": "Опт"}, headers=admin).json()
    resp = client.patch(
        f"/api/price-levels/{lvl['id']}", json={"name": "Закупка"}, headers=admin
    )
    assert resp.status_code == 409


def test_delete_level_in_use_409(client, db_session):
    from decimal import Decimal

    from app.catalog.models import CatalogItem, ItemPrice, PriceList, Supplier
    from app.orgs.models import Organization

    admin = make_admin(client, db_session)
    lvl = client.post("/api/price-levels", json={"name": "Розница"}, headers=admin).json()

    # Need org_id for supplier/item
    user = db_session.scalars(select(User).where(User.email == "admin@test.ru")).one()
    supplier = Supplier(name="S", org_id=user.org_id)
    db_session.add(supplier)
    db_session.commit()
    pl = PriceList(supplier_id=supplier.id, filename="f.xlsx", version=1, org_id=user.org_id)
    item = CatalogItem(supplier_id=supplier.id, name="X", org_id=user.org_id)
    db_session.add_all([pl, item])
    db_session.commit()
    db_session.add(
        ItemPrice(
            item_id=item.id,
            price_list_id=pl.id,
            price_level_id=lvl["id"],
            value=Decimal("10"),
        )
    )
    db_session.commit()
    resp = client.delete(f"/api/price-levels/{lvl['id']}", headers=admin)
    assert resp.status_code == 409


def test_non_admin_cannot_write_levels(client, db_session):
    from app.auth.models import User
    from app.core.security import hash_password

    make_admin(client, db_session)
    # После бутстрапа регистрация закрыта — создаём пользователя напрямую в БД
    u = User(
        email="user@test.ru",
        password_hash=hash_password("secret123"),
        name="Ю",
        role="estimator",
        status="active",
    )
    db_session.add(u)
    db_session.commit()
    user = {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}
    assert client.post("/api/price-levels", json={"name": "X"}, headers=user).status_code == 403
