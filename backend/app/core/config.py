"""Application configuration.

Environment-driven (12-factor). Never hard-code secrets. Separate
Development / Staging / Production via environment variables.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    app_name: str = "AbdulmajeedPharma (APH)"
    app_name_ar: str = "موسوعة عبدالمجيد للأدوية"
    app_version: str = "1.0.0"
    environment: str = "development"  # development | staging | production
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # --- Database ---
    # Production: postgresql+psycopg2://aph:secret@db:5432/aph
    # Development / tests may use sqlite:///./aph_dev.db
    database_url: str = "sqlite:///./aph_dev.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # --- Security ---
    secret_key: str = "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32"
    access_token_expire_minutes: int = 60 * 12
    refresh_token_expire_days: int = 14
    password_reset_expire_minutes: int = 30
    jwt_algorithm: str = "HS256"
    cors_origins: List[str] = ["*"]
    # Rate limiting (per client IP + route group)
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120
    rate_limit_auth_per_minute: int = 20

    # --- Storage (product images) ---
    storage_backend: str = "local"  # local | s3
    storage_local_root: str = "./storage"
    storage_s3_bucket: str = ""
    storage_s3_endpoint: str = ""
    storage_s3_access_key: str = ""
    storage_s3_secret_key: str = ""
    image_max_bytes: int = 8 * 1024 * 1024
    image_allowed_types: tuple = ("image/jpeg", "image/png", "image/webp")

    # --- Import engine ---
    import_upload_root: str = "./storage/imports"
    import_max_rows_per_batch: int = 1000

    # --- AI / RAG ---
    # "extractive" runs fully offline against the verified APH knowledge base
    # (no external provider, cannot hallucinate facts it did not retrieve).
    # "openai_compatible" enables an external LLM behind the same RAG + safety layer.
    ai_provider: str = "extractive"
    ai_openai_base_url: str = "https://api.openai.com/v1"
    ai_openai_api_key: str = ""  # never exposed to clients
    ai_openai_model: str = "gpt-4o-mini"
    ai_max_context_chars: int = 12000

    # --- Sync ---
    sync_page_size: int = 200

    # --- Observability ---
    log_level: str = "INFO"
    log_json: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
