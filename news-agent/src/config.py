from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field, validator


class NewsAgentSettings(BaseSettings):
    """
    Runtime configuration driven by environment variables.
    """

    openrouter_api_key: Optional[str] = Field(
        default=None, description="API key for OpenRouter DeepSeek access."
    )
    model: str = Field(
        default="deepseek/deepseek-v3.2", description="OpenRouter model identifier."
    )
    data_dir: Path = Field(
        default=Path("../data"),
        description="Shared directory where CSV outputs are written.",
        env="NEWS_AGENT_DATA_DIR",
    )
    referer: str = Field(
        default="https://nuah.local",
        description="Referer header required by OpenRouter.",
        env="NEWS_AGENT_REFERER",
    )
    app_title: str = Field(
        default="NUAH News Agent",
        description="X-Title header value for OpenRouter.",
        env="NEWS_AGENT_APP_TITLE",
    )
    top_tokens: int = Field(
        default=3, description="How many tokens to analyze per run."
    )
    min_confidence: float = Field(
        default=0.65,
        description="Minimum confidence score; below this we downgrade signal.",
    )
    freshness_minutes: int = Field(
        default=45, description="Maximum age (minutes) for news to be considered fresh."
    )
    timezone: str = Field(default="UTC", description="Timezone used for timestamps.")
    dry_run: bool = Field(
        default=False,
        description="If true, skip OpenRouter calls and synthesize deterministic data.",
    )
    cache_dir: Path = Field(
        default=Path("./cache"),
        description="Directory for caching API results.",
        env="NEWS_AGENT_CACHE_DIR",
    )
    cache_ttl_hours: int = Field(
        default=2,
        description="Cache time-to-live in hours.",
    )
    momentum_change_threshold: float = Field(
        default=0.10,
        description="Minimum momentum change (%) to trigger API call (Strategy 1: Smart Caching).",
    )
    volume_spike_threshold: float = Field(
        default=0.20,
        description="Minimum volume spike (%) to trigger API call.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @validator("data_dir", pre=True)
    def _expand_data_dir(cls, value: Path) -> Path:
        return Path(value).expanduser().resolve()

    @validator("cache_dir", pre=True)
    def _expand_cache_dir(cls, value: Path) -> Path:
        return Path(value).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> NewsAgentSettings:
    return NewsAgentSettings()

