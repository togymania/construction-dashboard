"""Structured logging + lightweight metrics (Faz 2.5 — Observability).

Gives the new matching / reconciliation pipeline the visibility the audit
asked for: how many rows matched, went to review, or were rejected, and
which parser failed — queryable instead of invisible.

Two pieces, both dependency-free:

* ``get_logger(name)`` returns a stdlib logger that emits **JSON lines**
  (ts, level, logger, msg + arbitrary structured fields) to stdout, so any
  aggregator (Grafana/Loki, CloudWatch, Datadog) can index them. Use
  ``log_event(logger, "msg", key=value, ...)`` to attach fields.
* ``metrics`` is a tiny thread-safe counter/gauge registry for pipeline
  events, exposable via an endpoint or scrape.

Sentry / OpenTelemetry are initialised only when their env vars *and*
packages are present (``init_observability``), so there is no hard
dependency and local/dev runs stay clean.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_CONFIGURED: set[str] = set()


class JsonFormatter(logging.Formatter):
    """Render each log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(name: str = "constructhub") -> logging.Logger:
    """Return a JSON-emitting logger, configured once per name."""
    logger = logging.getLogger(name)
    if name not in _CONFIGURED:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.handlers = [handler]
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        logger.propagate = False
        _CONFIGURED.add(name)
    return logger


def log_event(logger: logging.Logger, message: str, *, level: str = "info", **fields: Any) -> None:
    """Emit a structured event: ``log_event(log, "reconcile.apply", auto=812)``."""
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        message,
        extra={"extra_fields": fields},
    )


class MetricsRegistry:
    """Thread-safe in-process counters. Labels are folded into the key."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._lock = Lock()

    @staticmethod
    def _key(name: str, labels: dict[str, Any]) -> str:
        if not labels:
            return name
        suffix = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{suffix}}}"

    def incr(self, name: str, amount: float = 1.0, **labels: Any) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += amount

    def get(self, name: str, **labels: Any) -> float:
        with self._lock:
            return self._counters.get(self._key(name, labels), 0.0)

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return dict(self._counters)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


# Global registry used by the reconciliation engine and the parsers.
metrics = MetricsRegistry()


def record_reconciliation(auto: int, review: int, reject: int) -> None:
    """One call to log + count a reconciliation run's bucket totals."""
    metrics.incr("reconcile.auto", auto)
    metrics.incr("reconcile.review", review)
    metrics.incr("reconcile.reject", reject)
    log_event(
        get_logger(),
        "reconcile.run",
        auto=auto,
        review=review,
        reject=reject,
    )


def record_parser_error(parser: str, detail: str) -> None:
    """Count + log a parser failure so silent breakage becomes visible."""
    metrics.incr("parser.error", 1, parser=parser)
    log_event(get_logger(), "parser.error", level="error", parser=parser, detail=detail)


def init_observability() -> None:
    """Best-effort Sentry / OTel init — only if env + package are present.

    Never raises; absence of the optional packages is fine.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if dsn:
        try:  # pragma: no cover - optional dependency
            import sentry_sdk

            sentry_sdk.init(dsn=dsn, traces_sample_rate=0.1)
            log_event(get_logger(), "observability.sentry_enabled")
        except Exception:
            pass

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
        try:  # pragma: no cover - optional dependency
            from opentelemetry import trace  # noqa: F401

            log_event(get_logger(), "observability.otel_available")
        except Exception:
            pass
