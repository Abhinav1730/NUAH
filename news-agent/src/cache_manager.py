from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching of API results with change detection.
    Caches are stored as JSON files with metadata.
    """

    def __init__(self, cache_dir: Path, cache_ttl_hours: int = 2):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl_hours = cache_ttl_hours

    def get_cache_path(self, cache_key: str) -> Path:
        """Generate cache file path from key."""
        safe_key = cache_key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.json"

    def load_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Load cached data if it exists and is still valid.
        
        Returns:
            Cached data dict with 'data', 'timestamp', 'metadata' keys, or None if not found/invalid
        """
        cache_path = self.get_cache_path(cache_key)
        if not cache_path.exists():
            return None

        try:
            with cache_path.open("r", encoding="utf-8") as fp:
                cached = json.load(fp)

            cached_time = datetime.fromisoformat(cached["timestamp"].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - cached_time).total_seconds() / 3600

            if age_hours > self.cache_ttl_hours:
                logger.debug(f"Cache expired for {cache_key} (age: {age_hours:.1f}h)")
                return None

            logger.debug(f"Cache hit for {cache_key} (age: {age_hours:.1f}h)")
            return cached
        except Exception as e:
            logger.warning(f"Failed to load cache for {cache_key}: {e}")
            return None

    def save_cache(self, cache_key: str, data: Any, metadata: Optional[Dict] = None) -> None:
        """
        Save data to cache with timestamp and metadata.
        
        Args:
            cache_key: Unique identifier for this cache entry
            data: The data to cache (will be JSON-serialized)
            metadata: Optional metadata about the cached data
        """
        cache_path = self.get_cache_path(cache_key)
        cached = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
            "metadata": metadata or {},
        }

        try:
            with cache_path.open("w", encoding="utf-8") as fp:
                json.dump(cached, fp, indent=2)
            logger.debug(f"Cached data for {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to save cache for {cache_key}: {e}")

    def invalidate_cache(self, cache_key: str) -> None:
        """Delete a specific cache entry."""
        cache_path = self.get_cache_path(cache_key)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"Invalidated cache for {cache_key}")

    def clear_all(self) -> None:
        """Clear all cache files."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        logger.info("Cleared all cache files")

