from app.ai.models import AIModel, AIProvider, AIPurpose


def test_provider_model_purpose_chain(db_session):
    p = AIProvider(name="aitunnel", base_url="https://api.aitunnel.ru/v1",
                   auth_style="bearer", api_key_encrypted="enc")
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    assert p.enabled is True

    m = AIModel(provider_id=p.id, model_id="anthropic/claude-3.5-sonnet", label="Claude 3.5")
    db_session.add(m); db_session.commit(); db_session.refresh(m)
    assert m.enabled is True
    assert m.input_price is None

    purpose = AIPurpose(key="proposal_generation", title="Генерация КП",
                        primary_model_id=m.id)
    db_session.add(purpose); db_session.commit(); db_session.refresh(purpose)
    assert purpose.enabled is True
    assert purpose.fallback_model_id is None
