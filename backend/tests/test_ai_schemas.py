from app.ai import schemas


def test_provider_in_defaults():
    p = schemas.ProviderIn(name="vsegpt", base_url="https://api.vsegpt.ru/v1",
                           auth_style="x_api_key", api_key="sk-or-v1")
    assert p.enabled is True


def test_provider_out_has_no_key_field():
    # ключ никогда не отдаётся наружу — только has_key
    assert "api_key" not in schemas.ProviderOut.model_fields
    assert "api_key_encrypted" not in schemas.ProviderOut.model_fields
    assert "has_key" in schemas.ProviderOut.model_fields


def test_purpose_update_partial():
    body = schemas.PurposeUpdate(primary_model_id=5)
    assert body.model_dump(exclude_unset=True) == {"primary_model_id": 5}
