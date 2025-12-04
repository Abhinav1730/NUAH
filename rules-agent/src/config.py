from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field, validator


class RulesAgentSettings(BaseSettings):
    openrouter_api_key: Optional[str] = Field(default=None)
    model: str = Field(default="deepseek/deepseek-v3.2")
    data_dir: Path = Field(default=Path("../data"), env="RULES_AGENT_DATA_DIR")
    referer: str = Field(default="https://nuah.local", env="RULES_AGENT_REFERER")
    app_title: str = Field(default="NUAH Rules Agent", env="RULES_AGENT_APP_TITLE")
    dry_run: bool = Field(default=False)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @validator("data_dir", pre=True)
    def _expand(cls, value: Path) -> Path:
        return Path(value).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> RulesAgentSettings:
    return RulesAgentSettings()

