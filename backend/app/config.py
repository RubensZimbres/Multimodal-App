from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gcp_project: str = Field(default="", validation_alias="GOOGLE_CLOUD_PROJECT")
    # Gemini 3.x models are served from the global endpoint.
    gcp_location: str = Field(default="global", validation_alias="GOOGLE_CLOUD_LOCATION")

    # Model IDs live in config so a model retirement is an env change, not a code change.
    model_default: str = "gemini-3.8-flash"
    model_synthesis: str = "gemini-3.1-pro-preview"
    model_synthesis_fallback: str = "gemini-3.8-flash"

    alpha_vantage_api_key: str = ""
    alpha_vantage_base_url: str = "https://www.alphavantage.co/query"
    tool_response_char_limit: int = 20_000
    max_tool_rounds: int = 8

    # Bucket that receives user uploads (signed URLs).
    upload_bucket: str = ""
    upload_max_bytes: int = 200 * 1024 * 1024
    # Gemini may only read media under these prefixes; prevents the service account
    # from being used to read arbitrary objects it happens to have access to.
    demo_media_prefix: str = "gs://bucket-15-storage/"

    auth_required: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
