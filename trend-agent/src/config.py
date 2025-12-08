from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

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
    cache_dir: Path = Field(
        default=Path("./cache"),
        description="Directory for caching API results.",
        env="TREND_AGENT_CACHE_DIR",
    )
    cache_ttl_hours: int = Field(
        default=2,
        description="Cache time-to-live in hours.",
    )
    momentum_change_threshold: float = Field(
        default=0.15,
        description="Minimum momentum change (%) to trigger API call (Strategy 1: Smart Caching).",
    )
    volatility_threshold: float = Field(
        default=0.20,
        description="Minimum volatility to trigger API call.",
    )
    nuahchain_base_url: Optional[str] = Field(
        default="http://localhost:8080",
        description="Base URL for nuahchain-backend API.",
        env="NUAHCHAIN_API_BASE_URL",
    )
    nuahchain_api_token: Optional[str] = Field(
        default=None,
        description="JWT token for nuahchain-backend API (optional, for authenticated requests).",
        env="NUAHCHAIN_API_TOKEN",
    )
    use_real_data: bool = Field(
        default=True,
        description="If True, use real time-series data. If False, use CSV files only.",
        env="TREND_AGENT_USE_REAL_DATA",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @make_validator("data_dir", pre=True)
    @classmethod
    def _expand(cls, value) -> Path:
        if isinstance(value, str):
            value = Path(value)
        elif not isinstance(value, Path):
            value = Path(str(value))
        return value.expanduser().resolve()

    @make_validator("cache_dir", pre=True)
    @classmethod
    def _expand_cache_dir(cls, value) -> Path:
        if isinstance(value, str):
            value = Path(value)
        elif not isinstance(value, Path):
            value = Path(str(value))
        return value.expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> TrendAgentSettings:
    return TrendAgentSettings()

