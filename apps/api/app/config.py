"""App configuration via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GramBiz AI"
    app_env: str = "development"

    database_url: str = (
        "postgresql+psycopg://grambiz:grambiz@localhost:5432/grambiz"
    )

    llm_provider: str = "mock"  # mock | openai | anthropic
    llm_api_key: str = ""
    llm_model: str = ""

    embedding_mode: str = "tf_hash_v0"  # plan §21: deterministic offline embeddings
    rag_chunk_tokens: int = 420
    rag_chunk_overlap: int = 40

    map_style_url: str = "https://demotiles.maplibre.org/style.json"
    map_attribution: str = "© OpenStreetMap contributors"

    weather_api_key: str = ""
    market_price_api_key: str = ""
    data_provider_keys: str = ""

    overpass_url: str = "https://overpass-api.de/api/interpreter"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    rate_limit_rpm: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
