from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from the environment (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ultraball:ultraball@localhost:5432/ultraball"

    openai_api_key: str | None = None
    voyage_api_key: str | None = None
