"""Rule-based AI insight generator for subcontractor analysis.

Generates commentary, predictions, and alerts based on payment patterns,
contract timelines, and risk indicators. No LLM dependency.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from app.schemas.subcontractor import AIInsight


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_insights(
    subcontractor_name: str,
    contracts: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    risk_score: int,
) -> list[AIInsight]:
    """Generate rule-based insights for a subcontractor.

    Args:
        subcontractor_name: Display name
        contracts: List of contract dicts with keys:
            id, contract_amount, total_paid, start_date, end_date, status
        payments: List of payment dicts with keys:
            amount, payment_date, due_date, status, created_at
        risk_score: Aggregate risk score (0-100)

    Returns:
        List of AIInsight objects
    """
    insights: list[AIInsight] = []
    today = date.today()
    now = _now()

    # ---------- 1. Payment velocity analysis ----------
    recent_7d = [
        p for p in payments
        if p.get("status") == "paid"
        and p.get("payment_date")
        and (today - _to_date(p["payment_date"])).days <= 7
    ]
    recent_30d = [
        p for p in payments
        if p.get("status") == "paid"
        and p.get("payment_date")
        and (today - _to_date(p["payment_date"])).days <= 30
    ]

    sum_7d = sum(Decimal(str(p.get("amount", 0))) for p in recent_7d)
    sum_30d = sum(Decimal(str(p.get("amount", 0))) for p in recent_30d)

    if sum_30d > 0:
        daily_avg_30d = sum_30d / 30
        daily_avg_7d = sum_7d / 7 if sum_7d > 0 else Decimal("0")

        if daily_avg_30d > 0 and daily_avg_7d < daily_avg_30d * Decimal("0.8"):
            drop_pct = int((1 - float(daily_avg_7d / daily_avg_30d)) * 100)
            insights.append(AIInsight(
                type="commentary",
                severity="warning",
                message=f"{subcontractor_name} payment velocity dropped {drop_pct}% in the last 7 days",
                metric_value=float(drop_pct),
                generated_at=now,
            ))
        elif daily_avg_30d > 0 and daily_avg_7d > daily_avg_30d * Decimal("1.2"):
            increase_pct = int((float(daily_avg_7d / daily_avg_30d) - 1) * 100)
            insights.append(AIInsight(
                type="commentary",
                severity="info",
                message=f"{subcontractor_name} payment velocity increased {increase_pct}% in the last 7 days",
                metric_value=float(increase_pct),
                generated_at=now,
            ))

    # ---------- 2. Risk approach ----------
    if risk_score >= 70:
        insights.append(AIInsight(
            type="alert",
            severity="critical",
            message=f"{subcontractor_name} is at critical risk level (score: {risk_score}/100)",
            metric_value=float(risk_score),
            generated_at=now,
        ))
    elif risk_score >= 50:
        insights.append(AIInsight(
            type="alert",
            severity="warning",
            message=f"{subcontractor_name} is approaching risky threshold (score: {risk_score}/100)",
            metric_value=float(risk_score),
            generated_at=now,
        ))

    # ---------- 3. Per-contract predictions ----------
    for c in contracts:
        if c.get("status") != "active":
            continue

        contract_amount = Decimal(str(c.get("contract_amount", 0)))
        total_paid = Decimal(str(c.get("total_paid", 0)))
        remaining = contract_amount - total_paid
        end_date = _to_date(c.get("end_date", today.isoformat()))
        start_date = _to_date(c.get("start_date", today.isoformat()))

        days_elapsed = max((today - start_date).days, 1)
        days_remaining = (end_date - today).days

        if days_elapsed > 0 and total_paid > 0:
            daily_rate = total_paid / days_elapsed
            if daily_rate > 0 and remaining > 0:
                estimated_days_needed = int(remaining / daily_rate)
                delay = estimated_days_needed - max(days_remaining, 0)

                if delay > 0:
                    insights.append(AIInsight(
                        type="prediction",
                        severity="warning" if delay < 30 else "critical",
                        message=f"At this pace, contract #{c.get('id', '?')} will be {delay} days late",
                        metric_value=float(delay),
                        generated_at=now,
                    ))

        # Budget overrun prediction
        if contract_amount > 0 and total_paid > 0:
            paid_pct = float(total_paid / contract_amount * 100)
            elapsed_pct = float(days_elapsed / max((end_date - start_date).days, 1) * 100)

            if paid_pct > elapsed_pct * 1.3 and paid_pct > 50:
                overrun_prob = min(95, int(paid_pct - elapsed_pct + 30))
                insights.append(AIInsight(
                    type="prediction",
                    severity="warning",
                    message=f"Contract #{c.get('id', '?')} has a {overrun_prob}% budget-overrun risk",
                    metric_value=float(overrun_prob),
                    generated_at=now,
                ))

    # ---------- 4. Overdue payments ----------
    overdue_payments = [
        p for p in payments
        if p.get("due_date")
        and p.get("status") in ("pending", "approved")
        and _to_date(p["due_date"]) < today
    ]
    if overdue_payments:
        total_overdue = sum(Decimal(str(p.get("amount", 0))) for p in overdue_payments)
        insights.append(AIInsight(
            type="alert",
            severity="critical",
            message=f"{len(overdue_payments)} overdue payments detected (total: {total_overdue:,.0f} ₽)",
            metric_value=float(total_overdue),
            generated_at=now,
        ))

    # ---------- 5. Positive feedback ----------
    if risk_score < 20 and len(contracts) > 0:
        insights.append(AIInsight(
            type="commentary",
            severity="info",
            message=f"{subcontractor_name} is low-risk and healthy — performing well",
            metric_value=float(risk_score),
            generated_at=now,
            category="performance",
            source="rule",
        ))

    # ---------- 6. (Day 11) Capacity / pace projection per active contract ----------
    paid_payments = [p for p in payments if p.get("status") == "paid"]
    for c in contracts:
        if c.get("status") != "active":
            continue
        contract_amount = Decimal(str(c.get("contract_amount", 0)))
        total_paid = Decimal(str(c.get("total_paid", 0)))
        remaining = contract_amount - total_paid
        if contract_amount <= 0 or remaining <= 0:
            continue
        progress_pct = float(total_paid / contract_amount * 100)

        # Avg monthly pace from last 90 days of paid payments on this contract
        recent_90d = [
            p for p in paid_payments
            if p.get("payment_date")
            and (today - _to_date(p["payment_date"])).days <= 90
            and (p.get("contract_id") == c.get("id") or p.get("contract_id") is None)
        ]
        if recent_90d:
            sum_90d = sum(Decimal(str(p.get("amount", 0))) for p in recent_90d)
            monthly_pace = sum_90d / 3
            if monthly_pace > 0:
                months_to_finish = float(remaining / monthly_pace)
                end_date = _to_date(c.get("end_date", today.isoformat()))
                months_left = max(0, (end_date.year - today.year) * 12 + (end_date.month - today.month))
                if months_to_finish < months_left * 0.6:
                    insights.append(AIInsight(
                        type="commentary",
                        severity="info",
                        message=f"Contract #{c.get('id')} — {progress_pct:.0f}% remaining will be completed in approximately {months_to_finish:.1f} months at current pace (comfortable).",
                        metric_value=months_to_finish,
                        generated_at=now,
                        category="schedule",
                        title="Pace is healthy",
                        body=f"Remaining {remaining:,.0f} RUB, at the last-3-month average of {monthly_pace:,.0f} RUB/month, will finish in {months_to_finish:.1f} months. {months_left} months remain until contract end.",
                        source="rule",
                    ))
                elif months_to_finish > months_left and months_left > 0:
                    insights.append(AIInsight(
                        type="prediction",
                        severity="warning",
                        message=f"Contract #{c.get('id')} would take {months_to_finish:.1f} months at current pace, but only {months_left} months remain until end-date.",
                        metric_value=months_to_finish - months_left,
                        generated_at=now,
                        category="schedule",
                        title="Pace insufficient",
                        body=f"Remaining {remaining:,.0f} RUB, at current monthly pace ({monthly_pace:,.0f} RUB), will finish in {months_to_finish:.1f} months. {months_left} months remain until contract end.",
                        action="Either accelerate pace or initiate an end-date extension discussion.",
                        source="rule",
                    ))

    # ---------- 7. (Day 11) Avg payment delay (creation → paid) ----------
    paid_with_dates = [
        p for p in payments
        if p.get("status") == "paid" and p.get("payment_date") and p.get("created_at")
    ]
    if paid_with_dates:
        delays_days: list[int] = []
        for p in paid_with_dates:
            created = _to_date(p.get("created_at"))
            paid_date = _to_date(p.get("payment_date"))
            d = (paid_date - created).days
            if d >= 0:
                delays_days.append(d)
        if delays_days:
            avg_delay = sum(delays_days) / len(delays_days)
            if avg_delay > 25:
                insights.append(AIInsight(
                    type="commentary",
                    severity="warning" if avg_delay > 35 else "info",
                    message=f"{subcontractor_name} averages {avg_delay:.0f} days payment cycle — high vs. peers.",
                    metric_value=avg_delay,
                    generated_at=now,
                    category="financial",
                    title="Slow payment cycle",
                    body=f"Last {len(delays_days)} payments averaged {avg_delay:.0f} days each. Industry baseline ~12-15 days.",
                    action="Review the progress-payment approval workflow.",
                    source="rule",
                ))

    # ---------- 8. (Day 11) Mock LLM-style insight (will be replaced by real LLM) ----------
    if contracts and risk_score >= 30:
        # Synthetic LLM-style commentary that uses combined facts
        insights.append(AIInsight(
            type="commentary",
            severity="info",
            message=f"Additional review recommended for {subcontractor_name} — multiple risk indicators detected.",
            generated_at=now,
            category="risk",
            title="LLM mock — review recommended",
            body=(
                "This commentary was generated by the LLM mock (real LLM calls "
                "will activate once ANTHROPIC_API_KEY is added). Risk score, payment "
                "dynamics, and contract status were considered together."
            ),
            action="Add the API key and click 'Refresh' to get real LLM analysis.",
            source="llm_mock",
        ))

    return insights


def determine_overall_health(risk_score: int) -> str:
    """Map risk score to health status."""
    if risk_score >= 60:
        return "critical"
    elif risk_score >= 30:
        return "at_risk"
    return "good"


def _to_date(val: Any) -> date:
    """Convert a string or date to date."""
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return date.today()
