from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """
    Centralized configuration powered by pydantic.
    """

    sqlite_path: Path = Field(
        default=Path("../fetch-data-agent/data/user_data.db"),
        description="Path to fetch-data-agent SQLite database.",
    )
    snapshot_dir: Path = Field(
        default=Path("../fetch-data-agent/data/snapshots"),
        description="Directory containing JSON/TOON snapshots.",
    )
    api_base_url: str = Field(
        default="https://api.ndollar.org/api/v1",
        description="Base URL for n-dollar API.",
    )
    api_token: Optional[str] = Field(
        default=None, description="JWT token used for authenticated requests."
    )
    data_dir: Path = Field(
        default=Path("../data"),
        description="Shared directory where auxiliary agents write CSV outputs.",
    )
    models_dir: Path = Field(
        default=Path("./models"),
        description="Directory containing trained ML artifacts.",
    )
    user_ids: Optional[List[int]] = Field(
        default=None,
        description="Optional list of user IDs that should be processed every run.",
    )
    news_freshness_minutes: int = Field(default=45)
    trend_freshness_minutes: int = Field(default=60)
    snapshot_freshness_minutes: int = Field(default=30)
    dry_run: bool = Field(default=False)
    gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API key for final decision fusion."
    )
    gemini_model: str = Field(default="gemini-2.5-pro")
    decision_confidence_threshold: float = Field(default=0.7)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("snapshot_dir")
    def ensure_snapshot_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @validator("sqlite_path")
    def ensure_sqlite_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @validator("data_dir")
    def ensure_data_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @validator("models_dir")
    def ensure_models_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @validator("user_ids", pre=True)
    def parse_user_ids(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, list):
            return value
        return [
            int(part.strip())
            for part in str(value).split(",")
            if part.strip().isdigit()
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

