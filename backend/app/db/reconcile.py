"""Auto-Reconciliation Engine (Faz 1) — fix the unmatched ledger rows.

Runnable management command. Builds a dry-run reconciliation plan for a
project (see ``app.services.reconciliation``), reports the projected
match-rate lift, and -- only when asked -- applies the high-confidence
(AUTO) proposals. Every applied change is written to a timestamped audit
file so it can be undone.

Safety model:
  * Dry-run is the default; nothing is written without ``--apply``.
  * Apply only touches the AUTO tier (>= 90 score, unambiguous), and only
    sets a field that is currently NULL -- it never overwrites a value a
    human already entered.
  * ``--undo <file>`` reverts exactly the rows recorded in an audit file,
    and only if the value is still the one we set.

Usage:
    python -m app.db.reconcile --project-id 1                 # dry-run
    python -m app.db.reconcile --project-id 1 --apply         # apply AUTO
    python -m app.db.reconcile --undo reconcile_audit/2026....json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.observability import record_reconciliation
from app.db.session import AsyncSessionLocal
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.services.matching import Decision
from app.services.reconciliation import build_reconciliation_plan, match_rate

_AUDIT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reconcile_audit")


async def _counts(db) -> dict[str, int]:
    total = int(
        (await db.execute(select(func.count(LedgerEntry.id)))).scalar_one() or 0
    )
    budget_missing = int(
        (
            await db.execute(
                select(func.count(LedgerEntry.id)).where(
                    LedgerEntry.budget_code.is_(None)
                )
            )
        ).scalar_one()
        or 0
    )
    sub_missing = int(
        (
            await db.execute(
                select(func.count(LedgerEntry.id)).where(
                    LedgerEntry.subcontractor_id.is_(None),
                    LedgerEntry.entry_type == LedgerEntryType.EXPENSE,
                )
            )
        ).scalar_one()
        or 0
    )
    return {"total": total, "budget_missing": budget_missing, "sub_missing": sub_missing}


def _print_report(counts: dict[str, int], plan) -> None:
    total = counts["total"]
    st = plan.stats
    budget_now = total - counts["budget_missing"]
    sub_now = total - counts["sub_missing"]

    print("=" * 64)
    print("RECONCILIATION DRY-RUN")
    print("=" * 64)
    print(f"Ledger rows total            : {total}")
    print(f"Missing budget_code          : {counts['budget_missing']}")
    print(f"Missing subcontractor (exp.) : {counts['sub_missing']}")
    print("-" * 64)
    print("BUDGET CODE proposals")
    print(f"  auto   : {st.budget_auto}")
    print(f"  review : {st.budget_review}")
    print(f"  reject : {st.budget_reject}")
    print(f"  match-rate  now -> after AUTO : "
          f"{match_rate(budget_now, total)}% -> "
          f"{match_rate(budget_now + st.budget_auto, total)}%")
    print("-" * 64)
    print("SUBCONTRACTOR proposals")
    print(f"  auto   : {st.sub_auto}")
    print(f"  review : {st.sub_review}")
    print(f"  reject : {st.sub_reject}")
    print(f"  match-rate  now -> after AUTO : "
          f"{match_rate(sub_now, total)}% -> "
          f"{match_rate(sub_now + st.sub_auto, total)}%")
    print("-" * 64)
    print(f"AUTO total (applied with --apply) : {st.auto_total}")
    print(f"REVIEW total (needs a human)      : {st.review_total}")
    print("=" * 64)


async def run(project_id: int, apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        counts = await _counts(db)
        plan = await build_reconciliation_plan(db, project_id)
        _print_report(counts, plan)
        record_reconciliation(
            auto=plan.stats.auto_total,
            review=plan.stats.review_total,
            reject=plan.stats.budget_reject + plan.stats.sub_reject,
        )

        if not apply:
            print("\nDry-run only. Re-run with --apply to write the AUTO tier.")
            return

        audit: list[dict] = []
        auto = plan.proposals_for(Decision.AUTO)
        for row_id, proposal in auto:
            entry = (
                await db.execute(
                    select(LedgerEntry).where(LedgerEntry.id == row_id)
                )
            ).scalar_one_or_none()
            if entry is None:
                continue
            if proposal.field == "budget_code" and entry.budget_code is None:
                entry.budget_code = str(proposal.value)
                audit.append({"row_id": row_id, "field": "budget_code",
                              "old": None, "new": str(proposal.value)})
            elif (
                proposal.field == "subcontractor_id"
                and entry.subcontractor_id is None
            ):
                entry.subcontractor_id = int(proposal.value)
                audit.append({"row_id": row_id, "field": "subcontractor_id",
                              "old": None, "new": int(proposal.value)})

        await db.commit()

        os.makedirs(_AUDIT_DIR, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(_AUDIT_DIR, f"reconcile-{stamp}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {"project_id": project_id, "applied": len(audit), "changes": audit},
                fh,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nApplied {len(audit)} AUTO change(s).")
        print(f"Audit written to: {os.path.normpath(path)}")
        print("Undo with: python -m app.db.reconcile --undo <that file>")


async def undo(path: str) -> None:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    changes = data.get("changes", [])
    reverted = 0
    async with AsyncSessionLocal() as db:
        for ch in changes:
            entry = (
                await db.execute(
                    select(LedgerEntry).where(LedgerEntry.id == ch["row_id"])
                )
            ).scalar_one_or_none()
            if entry is None:
                continue
            field = ch["field"]
            current = getattr(entry, field)
            # Only revert if the value is still the one we set.
            if str(current) == str(ch["new"]):
                setattr(entry, field, ch["old"])
                reverted += 1
        await db.commit()
    print(f"Reverted {reverted} of {len(changes)} change(s) from {os.path.basename(path)}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ledger auto-reconciliation (Faz 1).")
    parser.add_argument("--project-id", type=int, help="Project whose budget items to match against.")
    parser.add_argument("--apply", action="store_true", help="Write the AUTO tier (default: dry-run).")
    parser.add_argument("--undo", metavar="AUDIT_FILE", help="Revert a previous apply from its audit file.")
    args = parser.parse_args()

    if args.undo:
        asyncio.run(undo(args.undo))
        return
    if args.project_id is None:
        parser.error("--project-id is required (unless using --undo).")
    asyncio.run(run(args.project_id, apply=args.apply))


if __name__ == "__main__":
    main()
