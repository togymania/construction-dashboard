"""Critical Path Method (Prompt 1 — redefine the critical path).

The old code called a contract "critical" if it ended within 30 days of
the project end. That is not the critical path. The **critical path** is
the chain of activities whose **Total Float = 0** — any slip on them slips
the whole project.

This implements the textbook CPM forward/backward pass over an activity
network (id, duration, predecessors), yielding ES/EF/LS/LF and Total Float
per activity, and the set of zero-float (critical) activities. Pure and
dependency-free.

The project has no activity/dependency model yet (the Schedule module is
still "coming soon"), so an adapter builds a degenerate network from
contracts; once a real schedule exists, the same engine drives it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_EPS = 1e-6


@dataclass(frozen=True)
class Activity:
    id: str
    duration: float
    predecessors: tuple[str, ...] = ()
    overdue_days: float = 0.0  # how late this activity already is (optional)


@dataclass
class CPMResult:
    es: dict[str, float] = field(default_factory=dict)
    ef: dict[str, float] = field(default_factory=dict)
    ls: dict[str, float] = field(default_factory=dict)
    lf: dict[str, float] = field(default_factory=dict)
    total_float: dict[str, float] = field(default_factory=dict)
    critical_ids: list[str] = field(default_factory=list)
    project_duration: float = 0.0


def compute_cpm(activities: list[Activity]) -> CPMResult:
    """Run the CPM forward/backward pass. Raises ``ValueError`` on a cycle
    or an unknown predecessor."""
    by_id = {a.id: a for a in activities}
    if not by_id:
        return CPMResult()
    for a in activities:
        for p in a.predecessors:
            if p not in by_id:
                raise ValueError(f"unknown predecessor {p!r} of {a.id!r}")

    # ---- Forward pass: ES / EF ----
    es: dict[str, float] = {}
    ef: dict[str, float] = {}
    visiting: set[str] = set()

    def forward(aid: str) -> float:
        if aid in ef:
            return ef[aid]
        if aid in visiting:
            raise ValueError("cycle detected in activity network")
        visiting.add(aid)
        act = by_id[aid]
        start = max((forward(p) for p in act.predecessors), default=0.0)
        es[aid] = start
        ef[aid] = start + act.duration
        visiting.discard(aid)
        return ef[aid]

    for aid in by_id:
        forward(aid)

    project_duration = max(ef.values())

    # ---- Successor map ----
    successors: dict[str, list[str]] = {aid: [] for aid in by_id}
    for a in activities:
        for p in a.predecessors:
            successors[p].append(a.id)

    # ---- Backward pass: LF / LS ----
    lf: dict[str, float] = {}
    ls: dict[str, float] = {}

    def backward(aid: str) -> float:
        if aid in ls:
            return ls[aid]
        succ = successors[aid]
        finish = (
            project_duration
            if not succ
            else min(backward(s) for s in succ)
        )
        lf[aid] = finish
        ls[aid] = finish - by_id[aid].duration
        return ls[aid]

    for aid in by_id:
        backward(aid)

    total_float = {aid: round(ls[aid] - es[aid], 6) for aid in by_id}
    critical = [aid for aid in by_id if abs(total_float[aid]) <= _EPS]

    return CPMResult(
        es=es, ef=ef, ls=ls, lf=lf,
        total_float=total_float,
        critical_ids=critical,
        project_duration=project_duration,
    )


def critical_path_delayed_days(
    activities: list[Activity], cpm: CPMResult | None = None
) -> float:
    """Max overdue days among the zero-float (critical) activities.

    A delay on a non-critical activity is absorbed by its float; only
    delays on the critical path push the finish date — that is what this
    reports.
    """
    cpm = cpm or compute_cpm(activities)
    crit = set(cpm.critical_ids)
    return max(
        (a.overdue_days for a in activities if a.id in crit and a.overdue_days > 0),
        default=0.0,
    )
