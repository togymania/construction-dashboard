"""In-memory cache for AI insights.

Process-local dict (lost on restart) — adequate for dev. The /ai-insights
endpoint reads/writes this so repeated page loads don't re-run rule-based
generation (or LLM calls) for the same subcontractor within a short window.

The cache key is `subcontractor_id`. Entries expire after `TTL_SECONDS`.
A `force_refresh=True` call (from a frontend "Refresh" button) bypasses the
cache and rewrites the entry.
"""
from __future__ import annotations

import time
from typing import Any

# 10 minutes — enough to soak up rapid page navigation without serving
# stale data after a payment is added.
TTL_SECONDS: int = 600

_store: dict[int, tuple[float, Any]] = {}


def get(subcontractor_id: int) -> Any | None:
    """Return cached insights or None if missing/expired."""
    entry = _store.get(subcontractor_id)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > TTL_SECONDS:
        _store.pop(subcontractor_id, None)
        return None
    return value


def set(subcontractor_id: int, value: Any) -> None:
    """Store insights for this subcontractor."""
    _store[subcontractor_id] = (time.time(), value)


def invalidate(subcontractor_id: int) -> None:
    """Remove the cache entry — call after payment add/edit/delete."""
    _store.pop(subcontractor_id, None)


def clear_all() -> None:
    """Wipe the whole cache (useful for tests)."""
    _store.clear()


def stats() -> dict:
    """Diagnostic snapshot — count + ages."""
    now = time.time()
    return {
        "size": len(_store),
        "ages_seconds": [round(now - ts) for ts, _ in _store.values()],
    }
