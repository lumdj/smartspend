"""
SmartSpend Settings
Loads and validates all configuration from environment variables at startup.
The app will refuse to start if required secrets are missing or malformed.
This prevents silent misconfiguration in production.
"""

from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, field_validator, model_validator
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    database_url: PostgresDsn

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: str

    # ── Data source ───────────────────────────────────────────────────────────
    data_source: Literal["synthetic", "plaid", "stripe"] = "synthetic"

    # ── App config ────────────────────────────────────────────────────────────
    environment: Literal["development", "production", "test"] = "development"
    allowed_origins: str = "http://localhost:5173"  # comma-separated in .env

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = 60

    # ── Derived properties ────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_key(cls, v: str) -> str:
        if not v.startswith("sk-ant-"):
            raise ValueError("ANTHROPIC_API_KEY appears invalid — must start with 'sk-ant-'")
        if len(v) < 20:
            raise ValueError("ANTHROPIC_API_KEY is too short to be valid")
        return v

    @field_validator("rate_limit_per_minute")
    @classmethod
    def validate_rate_limit(cls, v: int) -> int:
        if v < 1 or v > 1000:
            raise ValueError("rate_limit_per_minute must be between 1 and 1000")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Never log the settings object — it contains secrets
        # Use settings.is_production etc. individually


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    Cached so the .env file is only read once per process.
    Import and call this everywhere you need config:
        from config import get_settings
        settings = get_settings()
    """
    return Settings()
