from __future__ import annotations

import hashlib


class Store:
    """In-process content cache mapping file paths to (content, hash) tuples."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[str, str]] = {}

    @staticmethod
    def content_hash(content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def set(self, rel_path: str, content: str) -> None:
        """Store content and its hash in the cache."""
        hash_value = Store.content_hash(content)
        self._cache[rel_path] = (content, hash_value)

    def get(self, rel_path: str) -> tuple[str, str] | None:
        """Retrieve (content, hash) or None if not cached."""
        return self._cache.get(rel_path)

    def invalidate(self, rel_path: str) -> None:
        """Remove an entry from the cache (no-op if absent)."""
        self._cache.pop(rel_path, None)

    def invalidate_all(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
