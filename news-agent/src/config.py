from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older pydantic versions
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
        description="If True, fetch real data from nuahchain-backend. If False, use CSV files only.",
        env="NEWS_AGENT_USE_REAL_DATA",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @make_validator("data_dir", pre=True)
    @classmethod
    def _expand_data_dir(cls, value) -> Path:
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
def get_settings() -> NewsAgentSettings:
    return NewsAgentSettings()

