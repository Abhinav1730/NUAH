from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field, validator


class TrendAgentSettings(BaseSettings):
    openrouter_api_key: Optional[str] = Field(
        default=None, description="API key for OpenRouter DeepSeek access."
    )
    model: str = Field(default="deepseek/deepseek-v3.2")
    data_dir: Path = Field(default=Path("../data"), env="TREND_AGENT_DATA_DIR")
    referer: str = Field(default="https://nuah.local", env="TREND_AGENT_REFERER")
    app_title: str = Field(default="NUAH Trend Agent", env="TREND_AGENT_APP_TITLE")
    dry_run: bool = Field(default=False)
    max_tokens: int = Field(
        default=4, description="Max tokens to include per run (avoids prompt bloat)."
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @validator("data_dir", pre=True)
    def _expand(cls, value: Path) -> Path:
        return Path(value).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> TrendAgentSettings:
    return TrendAgentSettings()

