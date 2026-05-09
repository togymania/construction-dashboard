"""Tiny in-process cache of parsed import rows between /preview and /commit.

The wizard uploads → previews → user reviews matches → commits. Between those
two steps we hold the parsed rows server-side so the user doesn't have to
re-upload. For a demo this is acceptable; for HA we'd switch to Redis or
a temp DB table.

TTL: 1 hour. Items are dropped on get if expired.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from app.services.ledger_excel import ParsedLedgerRow


CACHE_TTL_SECONDS = 60 * 60  # 1 hour


@dataclass
class CachedImport:
    rows: list[ParsedLedgerRow]
    filename: str
    expires_at: float


_store: dict[str, CachedImport] = {}


def put(rows: list[ParsedLedgerRow], filename: str) -> str:
    """Store parsed rows; return an opaque token to retrieve them later."""
    _vacuum()
    token = uuid.uuid4().hex
    _store[token] = CachedImport(
        rows=rows,
        filename=filename,
        expires_at=time.time() + CACHE_TTL_SECONDS,
    )
    return token


def get(token: str) -> CachedImport | None:
    """Retrieve an import by token, or None if missing / expired."""
    item = _store.get(token)
    if item is None:
        return None
    if item.expires_at < time.time():
        _store.pop(token, None)
        return None
    return item


def discard(token: str) -> None:
    """Drop an import from cache (called after successful commit)."""
    _store.pop(token, None)


def _vacuum() -> None:
    """Remove expired entries; called opportunistically."""
    now = time.time()
    expired = [k for k, v in _store.items() if v.expires_at < now]
    for k in expired:
        _store.pop(k, None)
