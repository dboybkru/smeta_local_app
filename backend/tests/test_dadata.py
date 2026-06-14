import httpx

from app.auth.models import User
from app.clients import dadata
from app.core.security import create_access_token
from app.settings import service as settings_service


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_suggest_parties_maps_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Token tok"
        return httpx.Response(200, json={"suggestions": [{
            "value": "ПАО Сбербанк",
            "data": {"inn": "7707083893", "kpp": "773601001", "ogrn": "1027700132195",
                     "name": {"short_with_opf": "ПАО Сбербанк"},
                     "address": {"value": "г Москва"},
                     "management": {"name": "Греф Г.О."}, "type": "LEGAL",
                     "state": {"status": "ACTIVE"}}}]})
    http = httpx.Client(transport=httpx.MockTransport(handler))
    out = dadata.suggest_parties("tok", "сбер", http=http)
    assert out[0]["inn"] == "7707083893"
    assert out[0]["address"] == "г Москва"
    assert out[0]["management"] == "Греф Г.О."


def test_suggest_parties_network_error_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")
    http = httpx.Client(transport=httpx.MockTransport(handler))
    assert dadata.suggest_parties("tok", "x", http=http) == []


def test_clients_suggest_endpoint_no_token_empty(client, db_session):
    u = User(email="u@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    r = client.get("/api/clients/suggest?q=сбер", headers=_hdr(u))
    assert r.status_code == 200 and r.json() == []


def test_clients_suggest_endpoint_with_token(client, db_session, monkeypatch):
    u = User(email="u2@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    settings_service.set_secret(db_session, "dadata_token", "tok")
    monkeypatch.setattr(dadata, "suggest_parties",
                        lambda token, q, **k: [{"value": "X", "inn": "1"}])
    r = client.get("/api/clients/suggest?q=сбер", headers=_hdr(u))
    assert r.json()[0]["inn"] == "1"
