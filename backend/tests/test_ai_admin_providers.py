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
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: [
        {"id": "gpt-x", "input_price": None, "output_price": None},
        {"id": "claude-y", "input_price": None, "output_price": None},
        {"id": "gpt-x", "input_price": None, "output_price": None},
    ])
    r = client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2
    models = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()
    assert {m["model_id"] for m in models} == {"gpt-x", "claude-y"}
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    models2 = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()
    assert len(models2) == 2


def test_refresh_models_imports_pricing(client_app, db_session, monkeypatch):
    from decimal import Decimal
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: [
        {"id": "gpt-x", "input_price": Decimal("2.5"), "output_price": Decimal("10")},
    ])
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    m = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()[0]
    assert m["input_price"] == "2.5000"
    assert m["output_price"] == "10.0000"


def test_refresh_backfills_prices_on_existing(client_app, db_session, monkeypatch):
    from decimal import Decimal
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    # первый импорт — без цен
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: [
        {"id": "gpt-x", "input_price": None, "output_price": None}])
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    # повторный импорт — провайдер теперь отдаёт цены → backfill
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: [
        {"id": "gpt-x", "input_price": Decimal("2.5"), "output_price": Decimal("10")}])
    r = client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    assert r.json() == {"imported": 0, "updated": 1}
    m = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()[0]
    assert m["input_price"] == "2.5000"
    assert m["output_price"] == "10.0000"


def test_model_smoke_test_endpoint(client_app, db_session, monkeypatch):
    from app.ai.errors import AIError
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: [
        {"id": "gpt-x", "input_price": None, "output_price": None}])
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    mid = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()[0]["id"]

    monkeypatch.setattr(client, "chat_completion", lambda *args, **kw: {
        "content": "pong", "prompt_tokens": 1, "completion_tokens": 1, "cost_rub": None})
    ok = client_app.post(f"/api/ai/models/{mid}/test", headers=_hdr(a))
    assert ok.json() == {"ok": True, "detail": ""}

    def boom(*args, **kw):
        raise AIError("403 Forbidden")
    monkeypatch.setattr(client, "chat_completion", boom)
    bad = client_app.post(f"/api/ai/models/{mid}/test", headers=_hdr(a))
    assert bad.json()["ok"] is False
    assert "403" in bad.json()["detail"]


def test_delete_all_models_clears_purpose_refs(client_app, db_session, monkeypatch):
    from app.ai.models import AIPurpose
    a = _admin(db_session)
    db_session.add(AIPurpose(key="proposal_generation", title="КП"))
    db_session.commit()
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: [
        {"id": "gpt-x", "input_price": None, "output_price": None},
        {"id": "gpt-y", "input_price": None, "output_price": None}])
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    mid = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()[0]["id"]
    # назначить модель на цель, чтобы проверить обнуление ссылки
    client_app.put("/api/ai/purposes/proposal_generation", headers=_hdr(a),
                   json={"primary_model_id": mid})
    r = client_app.request("DELETE", "/api/ai/models", headers=_hdr(a))
    assert r.status_code == 200
    assert r.json() == {"deleted": 2}
    assert client_app.get("/api/ai/models", headers=_hdr(a)).json() == []
    purpose = next(p for p in client_app.get("/api/ai/purposes", headers=_hdr(a)).json()
                   if p["key"] == "proposal_generation")
    assert purpose["primary_model_id"] is None


def test_usage_summary_and_clear(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: [
        {"id": "gpt-x", "input_price": None, "output_price": None}])
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    mid = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()[0]["id"]
    monkeypatch.setattr(client, "chat_completion", lambda *args, **kw: {
        "content": "pong", "prompt_tokens": 3, "completion_tokens": 4, "cost_rub": "0.01"})
    client_app.post(f"/api/ai/models/{mid}/test", headers=_hdr(a))

    body = client_app.get("/api/ai/usage", headers=_hdr(a)).json()
    assert body["total_calls"] == 1
    assert body["by_model"][0]["model_id"] == "gpt-x"
    assert body["by_model"][0]["calls"] == 1
    assert body["by_model"][0]["prompt_tokens"] == 3
    assert body["total_cost_rub"] == "0.010000"

    assert client_app.delete("/api/ai/usage", headers=_hdr(a)).status_code == 204
    assert client_app.get("/api/ai/usage", headers=_hdr(a)).json()["total_calls"] == 0


# --- SSRF-валидатор base_url ---

def test_create_provider_rejects_metadata_url(client_app, db_session):
    """http://169.254.169.254/... должен вернуть 422."""
    a = _admin(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "evil", "base_url": "http://169.254.169.254/latest/meta-data/",
        "auth_style": "bearer", "api_key": "k"})
    assert r.status_code == 422


def test_create_provider_rejects_localhost(client_app, db_session):
    """http://localhost/... должен вернуть 422."""
    a = _admin(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "evil", "base_url": "http://localhost/v1",
        "auth_style": "bearer", "api_key": "k"})
    assert r.status_code == 422


def test_create_provider_rejects_ftp_scheme(client_app, db_session):
    """ftp://... должен вернуть 422."""
    a = _admin(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "evil", "base_url": "ftp://evil.example.com/v1",
        "auth_style": "bearer", "api_key": "k"})
    assert r.status_code == 422


def test_create_provider_rejects_file_scheme(client_app, db_session):
    """file:///etc/passwd должен вернуть 422."""
    a = _admin(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "evil", "base_url": "file:///etc/passwd",
        "auth_style": "bearer", "api_key": "k"})
    assert r.status_code == 422


def test_create_provider_accepts_valid_https(client_app, db_session):
    """Корректный https-URL проходит валидацию."""
    a = _admin(db_session)
    r = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "openai", "base_url": "https://api.openai.com/v1",
        "auth_style": "bearer", "api_key": "sk-ok"})
    assert r.status_code == 201


def test_update_provider_rejects_ssrf_base_url(client_app, db_session):
    """PUT /providers/{id} с http://127.0.0.1 → 422."""
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://api.example.com/v1",
        "auth_style": "bearer", "api_key": "k"}).json()["id"]
    r = client_app.put(f"/api/ai/providers/{pid}", headers=_hdr(a),
                       json={"base_url": "http://127.0.0.1/steal"})
    assert r.status_code == 422


def test_update_model_price(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    pid = client_app.post("/api/ai/providers", headers=_hdr(a), json={
        "name": "p", "base_url": "https://x/v1", "auth_style": "bearer",
        "api_key": "k"}).json()["id"]
    monkeypatch.setattr(client, "list_models", lambda prov, **kw: [
        {"id": "gpt-x", "input_price": None, "output_price": None}])
    client_app.post(f"/api/ai/providers/{pid}/models/refresh", headers=_hdr(a))
    mid = client_app.get(f"/api/ai/models?provider_id={pid}", headers=_hdr(a)).json()[0]["id"]
    r = client_app.put(f"/api/ai/models/{mid}", headers=_hdr(a),
                       json={"input_price": "15.5", "strengths": "быстрая"})
    assert r.status_code == 200
    assert r.json()["input_price"] == "15.5000"
    assert r.json()["strengths"] == "быстрая"
