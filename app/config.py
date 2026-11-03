from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from the environment (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ultraball:ultraball@localhost:5432/ultraball"

    openai_api_key: str | None = None
    voyage_api_key: str | None = None
    # The enrichment pass (Claude Sonnet 5.5). `CLAUDE_API_KEY` is the name the parse eval used.
    anthropic_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("anthropic_api_key", "claude_api_key")
    )
    # Sent as `anthropic-workspace-id`; only needed for a key not scoped to a workspace.
    anthropic_workspace_id: str | None = Field(
        default=None, validation_alias=AliasChoices("anthropic_workspace_id", "claude_workspace_id")
    )
