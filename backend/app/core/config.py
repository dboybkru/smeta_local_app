from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-change-me"
    database_url: str = "postgresql+psycopg://smeta:smeta@localhost:5432/smeta"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    yandex_client_id: str = ""
    yandex_client_secret: str = ""
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"


settings = Settings()
