import json

import pytest

from app.ai import client, crypto, service
from app.ai.errors import AIError, AINotConfigured
from app.ai.models import AIModel, AIProvider, AIPurpose


def _setup(db_session, *, with_fallback=False, provider_enabled=True):
    p = AIProvider(name="p1", base_url="https://x/v1", auth_style="bearer",
                   api_key_encrypted=crypto.encrypt("k"), enabled=provider_enabled)
    db_session.add(p); db_session.commit()
    m1 = AIModel(provider_id=p.id, model_id="primary", label="P")
    m2 = AIModel(provider_id=p.id, model_id="fallback", label="F")
    db_session.add_all([m1, m2]); db_session.commit()
    purpose = AIPurpose(key="proposal_generation", title="КП",
                        primary_model_id=m1.id,
                        fallback_model_id=m2.id if with_fallback else None)
    db_session.add(purpose); db_session.commit()
    return p, m1, m2


def test_call_llm_returns_text(db_session, monkeypatch):
    _setup(db_session)
    monkeypatch.setattr(client, "chat_completion",
                        lambda prov, mid, msgs, **kw: f"answer from {mid}")
    out = service.call_llm(db_session, "proposal_generation",
                           [{"role": "user", "content": "hi"}])
    assert out == "answer from primary"


def test_call_llm_json_parses_dict(db_session, monkeypatch):
    _setup(db_session)
    monkeypatch.setattr(client, "chat_completion",
                        lambda prov, mid, msgs, **kw: json.dumps({"title": "T"}))
    out = service.call_llm(db_session, "proposal_generation",
                           [{"role": "user", "content": "hi"}],
                           json_schema={"type": "object"})
    assert out == {"title": "T"}


def test_call_llm_fallback_on_primary_error(db_session, monkeypatch):
    _setup(db_session, with_fallback=True)

    def fake(prov, mid, msgs, **kw):
        if mid == "primary":
            raise AIError("primary down")
        return "from fallback"

    monkeypatch.setattr(client, "chat_completion", fake)
    out = service.call_llm(db_session, "proposal_generation",
                           [{"role": "user", "content": "hi"}])
    assert out == "from fallback"


def test_call_llm_both_fail_raises(db_session, monkeypatch):
    _setup(db_session, with_fallback=True)
    monkeypatch.setattr(client, "chat_completion",
                        lambda *a, **k: (_ for _ in ()).throw(AIError("down")))
    with pytest.raises(AIError):
        service.call_llm(db_session, "proposal_generation",
                         [{"role": "user", "content": "hi"}])


def test_call_llm_not_configured_when_no_primary(db_session):
    db_session.add(AIPurpose(key="proposal_generation", title="КП"))
    db_session.commit()
    with pytest.raises(AINotConfigured):
        service.call_llm(db_session, "proposal_generation",
                         [{"role": "user", "content": "hi"}])


def test_call_llm_not_configured_when_provider_disabled(db_session):
    _setup(db_session, provider_enabled=False)
    with pytest.raises(AINotConfigured):
        service.call_llm(db_session, "proposal_generation",
                         [{"role": "user", "content": "hi"}])


def test_call_llm_unknown_purpose_raises(db_session):
    with pytest.raises(AINotConfigured):
        service.call_llm(db_session, "nope", [{"role": "user", "content": "hi"}])
