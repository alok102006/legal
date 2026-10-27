import logging
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("legalos.config")

_DEV_JWT_SECRET = "dev-only-secret-change-me-before-production-0123456789"


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://legalos:legalos_secure_password@localhost:5432/legalos"
    )

    # Qdrant Vector Store
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: Optional[str] = Field(default=None)

    # LLM Provider: "gemini" | "local" | "fake" (fake is for tests only)
    llm_provider: str = Field(default="gemini")
    gemini_api_key: Optional[str] = Field(default=None)
    # Optional extra keys (comma-separated, from other Google projects). The free tier allows only
    # 20 requests per model per day per project, so a model that is used up on one key is retried on the next.
    gemini_api_keys: Optional[str] = Field(default=None)
    gemini_model: str = Field(default="gemini-2.5-flash")
    # Comma-separated models tried in order when the primary model is out of quota / unavailable.
    # Each model has its own daily free-tier quota. (gemini-2.5-flash-lite is retired for new keys.)
    gemini_fallback_models: str = Field(default="gemini-3.5-flash-lite,gemini-3.5-flash")
    llm_timeout_seconds: int = Field(default=120)
    llm_max_retries: int = Field(default=4)
    llm_max_concurrency: int = Field(default=3)
    llm_requests_per_minute: int = Field(default=10)
    llm_cache_enabled: bool = Field(default=True)
    llm_cache_dir: str = Field(default="./storage/llm_cache")

    # Vector collection used by the Documents workspace (tests use a separate one)
    documents_collection: str = Field(default="documents_v2")

    # Security / Dynamic CORS
    frontend_url: str = Field(default="http://localhost:5173")

    # Auth
    jwt_secret: str = Field(default=_DEV_JWT_SECRET)
    jwt_expire_minutes: int = Field(default=60 * 24 * 7)
    # Demo mode keeps the X-User-Role switcher working. Must be False in prod.
    demo_mode: bool = Field(default=True)

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

    # Live GST registry lookup for the Vendors workspace. Provider: "sandbox" | "generic" | "none" (empty = none,
    # or the legacy SANDBOX_CO_MODE=live setting above). Leave unset and supplier checks run offline only.
    gst_api_provider: Optional[str] = Field(default=None)
    gst_api_key: Optional[str] = Field(default=None)
    gst_api_secret: Optional[str] = Field(default=None)
    gst_api_base_url: Optional[str] = Field(default=None)
    gst_api_key_header: Optional[str] = Field(default=None)   # "generic" only; default x-api-key

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def fallback_models(self) -> list[str]:
        return [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]

    @property
    def gemini_keys(self) -> list[str]:
        """Primary key first, then the extra keys, without duplicates."""
        keys = [k.strip() for k in (self.gemini_api_keys or "").split(",") if k.strip()]
        if self.gemini_api_key and self.gemini_api_key not in keys:
            keys.insert(0, self.gemini_api_key)
        return keys


# Instantiate settings as a singleton
settings = Settings()

if settings.env == "prod" and settings.jwt_secret == _DEV_JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set to a strong random value when ENV=prod.")

# Never log secrets or full connection strings.
logger.info(
    "Settings loaded: env=%s llm_provider=%s model=%s sandbox_mode=%s demo_mode=%s",
    settings.env, settings.llm_provider, settings.gemini_model,
    settings.sandbox_co_mode, settings.demo_mode,
)
