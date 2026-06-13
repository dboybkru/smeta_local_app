from app.core.config import settings


def test_settings_defaults():
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.access_token_ttl_minutes == 30
    assert settings.refresh_token_ttl_days == 30


def test_anthropic_api_key_defaults_empty():
    from app.core.config import Settings

    s = Settings(_env_file=None)
    assert s.anthropic_api_key == ""
