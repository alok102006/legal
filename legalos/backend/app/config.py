from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://legalos:legalos_secure_password@localhost:5432/legalos"
    )

    # Qdrant Vector Store
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: Optional[str] = Field(default=None)

    # LLM Provider
    llm_provider: str = Field(default="gemini")  # "gemini" | "local"
    gemini_api_key: Optional[str] = Field(default=None)

    # Security / Dynamic CORS
    frontend_url: str = Field(default="http://localhost:5173")

    # Local Embeddings Cache Paths
    hf_home: str = Field(default="./model_cache")
    sentence_transformers_home: str = Field(default="./model_cache")

    # Environment
    env: str = Field(default="dev")  # "dev" | "prod"

    # Sandbox.co.in GSTIN API
    sandbox_co_mode: str = Field(default="mock")  # "mock" | "live"
    sandbox_co_api_key: Optional[str] = Field(default=None)
    sandbox_co_api_secret: Optional[str] = Field(default=None)
    sandbox_co_base_url: str = Field(default="https://api.sandbox.co.in")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# Instantiate settings as a singleton
settings = Settings()
print(f"DEBUG: Initialized Settings (env={settings.env})")
print(f"DEBUG: Database URL: {settings.database_url}")
print(f"DEBUG: Qdrant URL: {settings.qdrant_url}")
print(f"DEBUG: LLM Provider: {settings.llm_provider}")
print(f"DEBUG: Frontend URL (CORS): {settings.frontend_url}")
print(f"DEBUG: Sandbox.co.in Mode: {settings.sandbox_co_mode}")
print(f"DEBUG: Sandbox.co.in Base URL: {settings.sandbox_co_base_url}")
