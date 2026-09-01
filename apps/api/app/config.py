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

    llm_provider: str = "mock"  # mock | openai | nvidia
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""  # override for OpenAI-compatible providers (e.g. NVIDIA NIM)

    embedding_mode: str = "tf_hash_v0"  # plan §21: deterministic offline embeddings
    rag_chunk_tokens: int = 420
    rag_chunk_overlap: int = 40

    map_style_url: str = "https://demotiles.maplibre.org/style.json"
    map_attribution: str = "© OpenStreetMap contributors"

    weather_api_key: str = ""
    market_price_api_key: str = ""
    data_provider_keys: str = ""

    overpass_url: str = "https://overpass-api.de/api/interpreter"
    # Comma-separated fallback mirrors for competitor discovery (P0). The first
    # is tried, then the rest in order; all failing -> data_status UNAVAILABLE.
    overpass_mirrors: str = (
        "https://overpass-api.de/api/interpreter,"
        "https://overpass.kumi.systems/api/interpreter,"
        "https://overpass.private.coffee/api/interpreter"
    )
    overpass_timeout_s: int = 40

    # Geocoder (place / address search for the exact proposed shop location).
    # Provider is configurable; official API keys stay server-side only.
    geocoder_provider: str = "nominatim"  # nominatim | photon | google
    geocoder_base_url: str = ""  # empty -> provider default
    geocoder_api_key: str = ""
    geocoder_user_agent: str = "GramBiz AI (Smart India Hackathon 2026)"
    geocoder_timeout_s: int = 10
    # Geographic TTL cache (P0): how long a competitor result for a geo-bucket
    # is reused before a live refresh, and the lat/lon bucket size in km.
    competitor_cache_ttl_hours: float = 24.0
    competitor_cache_bucket_km: int = 1
    # Fail fast vs fallback to stale cache when Overpass is down.
    competitor_allow_stale_on_failure: bool = True

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    rate_limit_rpm: int = 60

    # Data-Provider API keys (never commit real values; set in .env)
    data_gov_api_key: str = ""  # https://data.gov.in/help/how-use-data-govin-apis
    imd_api_key: str = ""
    imd_rainfall_resource: str = ""  # confirmed data.gov.in resource id for IMD rainfall
    data_gov_market_resource: str = ""  # confirmed data.gov.in resource id for market prices
    soil_health_resource: str = ""  # confirmed data.gov.in resource id for Soil Health Card nutrient analysis
    udyam_resource: str = ""  # confirmed data.gov.in resource id for the UDYAM MSME unit list
    udyam_pincode_directory: str = ""  # path to CSV: pincode,latitude,longitude for pincode->centroid

    # Decision-logic thresholds (Phase 12). Opportunity score vs data confidence:
    confidence_medium_at: float = 40.0  # confidence < this -> low
    confidence_high_at: float = 70.0    # confidence >= this -> high
    opportunity_go_above: float = 65.0      # overall score >= this to consider GO
    opportunity_avoid_below: float = 45.0   # overall score < this -> AVOID
    finance_fit_go_min: float = 60.0        # financial-fit score needed for GO
    risk_go_max: float = 55.0               # risk score above this blocks GO
    risk_avoid_above: float = 80.0          # risk score >= this -> AVOID
    finance_avoid_below: float = 40.0       # financial-fit < this -> AVOID

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
