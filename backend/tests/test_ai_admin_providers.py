import httpx

from app.ai import client
from app.auth.models import User
from app.core.security import create_access_token


def _admin(db_session):
    u = User(email="adm@x.ru", name="A", role="admin", status="active")
    db_session.add(u); db_session.commit(); return u


def _estimator(db_session):
    u = User(email="est@x.ru", name="E", role="estimator", status="active")
    db_session.add(u); db_session.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def test_create_provider_hides_key(client_app, db_session):
    a = _admin(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "aitunnel", "base_url": "https://api.aitunnel.ru/v1",
        "auth_style": "bearer", "api_key": "sk-aitunnel-secret"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_key"] is True
    assert "api_key" not in body and "api_key_encrypted" not in body
    lst = client_app.get("/api/ai/providers", headers=_hdr(a)).json()
    assert lst[0]["has_key"] is True
    assert "api_key" not in lst[0]


def test_update_provider_keeps_key_when_omitted(client_app, db_session):
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "sk-1"}).json()["id"]
    r = client_app.put(f"/api/ai/providers/{pid}", headers=_hdr(a),
                       json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert r.json()["has_key"] is True


def test_provider_requires_admin(client_app, db_session):
    e = _estimator(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(e), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer", "api_key": "k"})
    assert r.status_code == 403


def test_refresh_models_imports_ids(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: ["gpt-x", "claude-y", "gpt-x"])
    r = client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2
    models = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()
    assert {m["model_id"] for m in models} == {"gpt-x", "claude-y"}
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    models2 = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()
    assert len(models2) == 2


def test_update_model_price(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: ["gpt-x"])
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    mid = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()[0]["id"]
    r = client_app.put(f"/api/ai/models/{mid}", headers=_hdr(a),
                       json={"input_price": "15.5", "strengths": "быстрая"})
    assert r.status_code == 200
    assert r.json()["input_price"] == "15.5000"
    assert r.json()["strengths"] == "быстрая"
