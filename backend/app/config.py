from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"

    aoai_endpoint: str = ""
    aoai_api_key: str = ""
    aoai_api_version: str = "2024-08-01-preview"
    aoai_gpt4o_deployment: str = "gpt-4o"
    aoai_gpt4o_mini_deployment: str = "gpt-4o-mini"
    aoai_embedding_deployment: str = "text-embedding-3-large"
    aoai_embedding_dimensions: int = 1536

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/recruiter"

    # Optional split form (used in Azure where the password is a KV secret).
    # If POSTGRES_HOST is set we compose DATABASE_URL at startup from these.
    postgres_host: str = ""
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_database: str = "recruiter"
    postgres_ssl: str = ""  # e.g. "require"

    cors_allow_origins: str = "http://localhost:3000"

    candidate_pool_size: int = Field(default=500, ge=10, le=5000)
    rerank_top_k: int = Field(default=50, ge=10, le=200)
    rerank_batch_size: int = Field(default=10, ge=1, le=25)
    outreach_top_k: int = Field(default=20, ge=1, le=50)
    max_conversation_turns: int = Field(default=4, ge=1, le=10)

    persona_temperature: float = 0.7
    recruiter_temperature: float = 0.4

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        if self.postgres_host:
            ssl = f"?ssl={self.postgres_ssl}" if self.postgres_ssl else ""
            return (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:5432/{self.postgres_database}{ssl}"
            )
        return self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
