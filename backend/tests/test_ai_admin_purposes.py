from app.ai import router_advisor, service
from app.ai.models import AIModel, AIProvider, AIPurpose
from app.auth.models import User
from app.core.security import create_access_token


def _admin(db_session):
    u = User(email="adm@x.ru", name="A", role="admin", status="active")
    db_session.add(u); db_session.commit(); return u


def _hdr(u):
    return {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _seed_purpose_and_model(db_session):
    db_session.add(AIPurpose(key="proposal_generation", title="КП"))
    p = AIProvider(name="p", base_url="https://x/v1", auth_style="bearer",
                   api_key_encrypted="enc")
    db_session.add(p); db_session.commit()
    m = AIModel(provider_id=p.id, model_id="m1", label="M1")
    db_session.add(m); db_session.commit()
    return m


def test_list_and_update_purpose(client_app, db_session):
    a = _admin(db_session)
    m = _seed_purpose_and_model(db_session)
    lst = client_app.get("/api/ai/purposes", headers=_hdr(a)).json()
    assert any(x["key"] == "proposal_generation" for x in lst)
    r = client_app.put("/api/ai/purposes/proposal_generation", headers=_hdr(a),
                       json={"primary_model_id": m.id})
    assert r.status_code == 200, r.text
    assert r.json()["primary_model_id"] == m.id


def test_update_unknown_purpose_404(client_app, db_session):
    a = _admin(db_session)
    assert client_app.put("/api/ai/purposes/nope", headers=_hdr(a),
                          json={"enabled": False}).status_code == 404


def test_router_recommend_returns_suggestions(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    _seed_purpose_and_model(db_session)
    monkeypatch.setattr(router_advisor, "recommend_models",
                        lambda db: [{"purpose_key": "proposal_generation",
                                     "provider": "p", "model_id": "m1", "rationale": "ok"}])
    r = client_app.post("/api/ai/router/recommend", headers=_hdr(a))
    assert r.status_code == 200, r.text
    assert r.json()[0]["model_id"] == "m1"


def test_purpose_test_endpoint_ok(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    _seed_purpose_and_model(db_session)
    monkeypatch.setattr(service, "call_llm", lambda *a, **k: "pong")
    r = client_app.post("/api/ai/purposes/proposal_generation/test", headers=_hdr(a))
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_purpose_test_endpoint_reports_error(client_app, db_session, monkeypatch):
    a = _admin(db_session)
    _seed_purpose_and_model(db_session)
    from app.ai.errors import AINotConfigured
    def boom(*a, **k):
        raise AINotConfigured("нет модели")
    monkeypatch.setattr(service, "call_llm", boom)
    r = client_app.post("/api/ai/purposes/proposal_generation/test", headers=_hdr(a))
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "нет модели" in r.json()["detail"]
