"""Settings entrypoint — pydantic-settings based.

D-8: pydantic-settings 사용. 우선순위 = init 인자 > OS env > .env > 기본값.
D-12: 모듈 레벨에서 Settings() 인스턴스화 금지 (lazy). 호출 시점에 생성.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    google_api_key: str

    log_level: str = "INFO"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5435/best_agent_base"
    )

    agent_state_dir: str = "./.agent_state"

    redis_url: str | None = None

    blob_store_url: str | None = None
