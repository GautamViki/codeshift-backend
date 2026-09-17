import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Any


class TranspilationCache:
    """Thread-safe In-Memory LRU Cache with TTL for transpilation results."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 86400):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def generate_key(source_code: str, source_language: str, target_language: str) -> str:
        content = f"{source_language.strip().lower()}::{target_language.strip().lower()}::{source_code.strip()}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._cache:
                return None

            created_at, value = self._cache[key]
            if time.time() - created_at > self.ttl_seconds:
                del self._cache[key]
                return None

            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (time.time(), value)

            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


transpile_cache = TranspilationCache()
