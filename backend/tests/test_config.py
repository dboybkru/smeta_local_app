from app.core.config import settings


def test_settings_defaults():
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.access_token_ttl_minutes == 30
    assert settings.refresh_token_ttl_days == 30
