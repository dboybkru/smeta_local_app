from app.ai import router_advisor, service
from app.ai.models import AIModel, AIProvider, AIPurpose


def _catalog(db_session):
    p = AIProvider(name="aitunnel", base_url="https://x/v1", auth_style="bearer",
                   api_key_encrypted="enc")
    db_session.add(p); db_session.commit()
    db_session.add(AIModel(provider_id=p.id, model_id="cheap", label="Cheap",
                           input_price=10, strengths="дёшево"))
    db_session.add(AIPurpose(key="proposal_generation", title="КП",
                             description="тексты КП"))
    db_session.commit()


def test_recommend_models_builds_prompt_and_returns(db_session, monkeypatch):
    _catalog(db_session)
    seen = {}

    def fake_call(db, key, messages, **kw):
        seen["key"] = key
        seen["prompt"] = messages[-1]["content"]
        return {"recommendations": [
            {"purpose_key": "proposal_generation", "provider": "aitunnel",
             "model_id": "cheap", "rationale": "оптимально по цене"}
        ]}

    monkeypatch.setattr(service, "call_llm", fake_call)
    recs = router_advisor.recommend_models(db_session)
    assert seen["key"] == "router"          # советует модель цели "router"
    assert "cheap" in seen["prompt"]        # каталог в промпте
    assert "proposal_generation" in seen["prompt"]  # цели в промпте
    assert recs[0]["model_id"] == "cheap"
    assert recs[0]["rationale"]
