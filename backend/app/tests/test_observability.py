"""Tests for structured logging + metrics (Faz 2.5 — Observability)."""
from __future__ import annotations

import json
import logging

from app.core.observability import (
    JsonFormatter,
    MetricsRegistry,
    get_logger,
    log_event,
    metrics,
    record_reconciliation,
)


class TestJsonFormatter:
    def _record(self, msg="hello", fields=None):
        rec = logging.LogRecord(
            name="t", level=logging.INFO, pathname=__file__, lineno=1,
            msg=msg, args=(), exc_info=None,
        )
        if fields:
            rec.extra_fields = fields
        return rec

    def test_emits_valid_json_with_core_fields(self):
        out = JsonFormatter().format(self._record())
        obj = json.loads(out)
        assert obj["level"] == "INFO"
        assert obj["logger"] == "t"
        assert obj["msg"] == "hello"
        assert "ts" in obj

    def test_extra_fields_are_merged(self):
        out = JsonFormatter().format(
            self._record(fields={"auto": 812, "parser": "ledger"})
        )
        obj = json.loads(out)
        assert obj["auto"] == 812
        assert obj["parser"] == "ledger"

    def test_unicode_preserved(self):
        out = JsonFormatter().format(self._record(msg="Монарт"))
        assert "Монарт" in out


class TestGetLogger:
    def test_idempotent_single_handler(self):
        a = get_logger("dup_test")
        b = get_logger("dup_test")
        assert a is b
        assert len(a.handlers) == 1

    def test_log_event_does_not_raise(self):
        log_event(get_logger("evt"), "reconcile.apply", auto=10, review=3)


class TestMetricsRegistry:
    def test_incr_and_get(self):
        r = MetricsRegistry()
        r.incr("x")
        r.incr("x", 4)
        assert r.get("x") == 5.0

    def test_labels_are_separate_series(self):
        r = MetricsRegistry()
        r.incr("parser.error", parser="ledger")
        r.incr("parser.error", parser="budget")
        r.incr("parser.error", parser="ledger")
        assert r.get("parser.error", parser="ledger") == 2.0
        assert r.get("parser.error", parser="budget") == 1.0

    def test_snapshot_and_reset(self):
        r = MetricsRegistry()
        r.incr("a")
        snap = r.snapshot()
        assert snap["a"] == 1.0
        r.reset()
        assert r.get("a") == 0.0

    def test_missing_metric_is_zero(self):
        assert MetricsRegistry().get("nope") == 0.0


class TestRecordReconciliation:
    def test_counts_buckets(self):
        metrics.reset()
        record_reconciliation(auto=800, review=120, reject=50)
        assert metrics.get("reconcile.auto") == 800
        assert metrics.get("reconcile.review") == 120
        assert metrics.get("reconcile.reject") == 50
