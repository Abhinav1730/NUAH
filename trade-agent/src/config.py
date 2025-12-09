from functools import lru_cache
from pathlib import Path
from typing import List, Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

from pydantic import Field

# Handle both Pydantic v1 and v2 validator syntax
# Try Pydantic v2 first (field_validator)
_field_validator = None
_validator = None

try:
    from pydantic import field_validator
    _field_validator = field_validator
except (ImportError, AttributeError):
    pass

# Try Pydantic v1 (validator)
if _field_validator is None:
    try:
        from pydantic import validator
        _validator = validator
    except (ImportError, AttributeError):
        pass

# Create make_validator function based on what's available
if _field_validator is not None:
    # Pydantic v2
    def make_validator(field_name, pre=True):
        def decorator(func):
            return _field_validator(field_name, mode="before" if pre else "after")(func)
        return decorator
elif _validator is not None:
    # Pydantic v1 - allow reuse so repeated imports during tests don't error
    def make_validator(field_name, pre=True):
        def decorator(func):
            return _validator(field_name, pre=pre, allow_reuse=True)(func)
        return decorator
else:
    # Fallback - no validation (shouldn't happen, but safe)
    def make_validator(field_name, pre=True):
        def decorator(func):
            return func
        return decorator


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
        default="http://localhost:8080",
        description="Base URL for nuahchain-backend API.",
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
    
    # Batch processing settings
    batch_size: int = Field(
        default=50,
        description="Number of users to process per batch. Set to 0 for no batching.",
    )
    batch_delay_seconds: int = Field(
        default=5,
        description="Seconds to wait between batches to avoid overloading.",
    )
    gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API key for final decision fusion."
    )
    gemini_model: str = Field(default="gemini-2.5-pro")
    decision_confidence_threshold: float = Field(default=0.7)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env variables like NUAHCHAIN_API_*

    @make_validator("snapshot_dir", pre=True)
    @classmethod
    def ensure_snapshot_dir(cls, value) -> Path:
        if isinstance(value, str):
            value = Path(value)
        elif not isinstance(value, Path):
            value = Path(str(value))
        return value.expanduser().resolve()

    @make_validator("sqlite_path", pre=True)
    @classmethod
    def ensure_sqlite_path(cls, value) -> Path:
        if isinstance(value, str):
            value = Path(value)
        elif not isinstance(value, Path):
            value = Path(str(value))
        return value.expanduser().resolve()

    @make_validator("data_dir", pre=True)
    @classmethod
    def ensure_data_dir(cls, value) -> Path:
        if isinstance(value, str):
            value = Path(value)
        elif not isinstance(value, Path):
            value = Path(str(value))
        return value.expanduser().resolve()

    @make_validator("models_dir", pre=True)
    @classmethod
    def ensure_models_dir(cls, value) -> Path:
        if isinstance(value, str):
            value = Path(value)
        elif not isinstance(value, Path):
            value = Path(str(value))
        return value.expanduser().resolve()

    @make_validator("user_ids", pre=True)
    @classmethod
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

