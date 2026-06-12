def make_admin(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "admin@test.ru", "password": "secret123", "name": "А"},
    )
    assert resp.status_code == 201
    resp = client.post(
        "/api/auth/login", json={"email": "admin@test.ru", "password": "secret123"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_admin_creates_and_lists_levels(client):
    admin = make_admin(client)
    resp = client.post(
        "/api/price-levels", json={"name": "Закупка", "sort_order": 1}, headers=admin
    )
    assert resp.status_code == 201
    client.post("/api/price-levels", json={"name": "Розница", "sort_order": 2}, headers=admin)
    resp = client.get("/api/price-levels", headers=admin)
    assert [lvl["name"] for lvl in resp.json()] == ["Закупка", "Розница"]


def test_duplicate_level_name_409(client):
    admin = make_admin(client)
    client.post("/api/price-levels", json={"name": "Опт"}, headers=admin)
    resp = client.post("/api/price-levels", json={"name": "Опт"}, headers=admin)
    assert resp.status_code == 409


def test_rename_level(client):
    admin = make_admin(client)
    lvl = client.post("/api/price-levels", json={"name": "Опт"}, headers=admin).json()
    resp = client.patch(
        f"/api/price-levels/{lvl['id']}", json={"name": "Опт 2026"}, headers=admin
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Опт 2026"


def test_delete_level(client):
    admin = make_admin(client)
    lvl = client.post("/api/price-levels", json={"name": "Врем"}, headers=admin).json()
    assert client.delete(f"/api/price-levels/{lvl['id']}", headers=admin).status_code == 204
    assert client.get("/api/price-levels", headers=admin).json() == []


def test_rename_to_existing_name_409(client):
    admin = make_admin(client)
    client.post("/api/price-levels", json={"name": "Закупка"}, headers=admin)
    lvl = client.post("/api/price-levels", json={"name": "Опт"}, headers=admin).json()
    resp = client.patch(
        f"/api/price-levels/{lvl['id']}", json={"name": "Закупка"}, headers=admin
    )
    assert resp.status_code == 409


def test_delete_level_in_use_409(client, db_session):
    from decimal import Decimal

    from app.catalog.models import CatalogItem, ItemPrice, PriceList, Supplier

    admin = make_admin(client)
    lvl = client.post("/api/price-levels", json={"name": "Розница"}, headers=admin).json()
    supplier = Supplier(name="S")
    db_session.add(supplier)
    db_session.commit()
    pl = PriceList(supplier_id=supplier.id, filename="f.xlsx", version=1)
    item = CatalogItem(supplier_id=supplier.id, name="X")
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


def test_non_admin_cannot_write_levels(client):
    make_admin(client)
    client.post(
        "/api/auth/register",
        json={"email": "user@test.ru", "password": "secret123", "name": "Ю"},
    )
    resp = client.post("/api/auth/login", json={"email": "user@test.ru", "password": "secret123"})
    user = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert client.post("/api/price-levels", json={"name": "X"}, headers=user).status_code == 403
