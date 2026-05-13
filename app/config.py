from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://arbitration:arbitration_secret@localhost:5432/legal_arbitration"

    # Groq API
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    # Security
    encryption_key: str  # Fernet key (base64, 32 bytes)
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
