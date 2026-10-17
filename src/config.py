"""Environment & settings loader backed by pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openlibrary_base_url: str = "https://openlibrary.org"
    request_timeout_seconds: float = 10.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    rate_limit_requests_per_second: float = 2.0

    database_path: str = "data/outputs/library.db"
    cache_ttl_seconds: int = 86_400

    reports_output_dir: str = "data/outputs"

    log_level: str = "INFO"


settings = Settings()
