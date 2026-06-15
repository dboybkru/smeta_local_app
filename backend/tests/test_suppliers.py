from tests.test_price_levels import make_admin


def test_create_and_list_suppliers(client, db_session):
    admin = make_admin(client, db_session)
    resp = client.post("/api/suppliers", json={"name": "Bolid"}, headers=admin)
    assert resp.status_code == 201
    assert resp.json()["column_mapping_template"] is None
    client.post("/api/suppliers", json={"name": "Optimus"}, headers=admin)
    names = [s["name"] for s in client.get("/api/suppliers", headers=admin).json()]
    assert names == ["Bolid", "Optimus"]


def test_duplicate_supplier_409(client, db_session):
    admin = make_admin(client, db_session)
    client.post("/api/suppliers", json={"name": "Bolid"}, headers=admin)
    assert client.post("/api/suppliers", json={"name": "Bolid"}, headers=admin).status_code == 409
