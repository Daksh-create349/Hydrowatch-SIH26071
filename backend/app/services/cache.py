"""Lightweight in-memory cache abstraction with TTL."""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, Optional, Tuple


class DataCache:
    """Thread-safe in-memory cache with time-to-live (TTL) expiration."""

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl_seconds = default_ttl_seconds
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve unexpired value for key, or None."""
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            if key not in self._store:
                return None
            val, expiry = self._store[key]
            if now > expiry:
                del self._store[key]
                return None
            return val

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store value with TTL expiration."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expiry = datetime.now(timezone.utc).timestamp() + ttl
        with self._lock:
            self._store[key] = (value, expiry)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()


# Global singleton instance for data layer
cache = DataCache(default_ttl_seconds=300)
