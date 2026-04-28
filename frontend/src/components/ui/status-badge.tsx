"use client";

import { cn } from "@/lib/utils";

type BadgeColor = "green" | "amber" | "red" | "blue" | "gray" | "purple";

const COLOR_CLASSES: Record<BadgeColor, string> = {
  green:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900",
  amber:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border-amber-200 dark:border-amber-900",
  red:
    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border-red-200 dark:border-red-900",
  blue:
    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200 dark:border-blue-900",
  gray:
    "bg-slate-100 text-slate-600 dark:bg-slate-900/30 dark:text-slate-400 border-slate-200 dark:border-slate-800",
  purple:
    "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 border-purple-200 dark:border-purple-900",
};

interface Props {
  /** The raw status value (e.g. "active", "draft"). Used as the rendered label by default. */
  status: string;
  /** Maps each known status to a color preset. Unknown statuses fall back to gray. */
  colorMap: Record<string, BadgeColor>;
  /** Optional override for the displayed label (default: pretty-printed status). */
  label?: string;
  className?: string;
}

/**
 * Small, theme-aware status badge.
 *
 * Usage:
 *   <StatusBadge
 *     status={subcontractor.status}
 *     colorMap={{ active: "green", suspended: "amber", blacklisted: "red" }}
 *   />
 */
export function StatusBadge({ status, colorMap, label, className }: Props) {
  const color = colorMap[status] ?? "gray";
  const text = label ?? prettify(status);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium",
        COLOR_CLASSES[color],
        className
      )}
    >
      {text}
    </span>
  );
}

function prettify(s: string): string {
  // "on_hold" -> "On Hold", "active" -> "Active"
  return s
    .split(/[_\s]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// ---------------- Preset color maps for common domains ----------------

export const SUBCONTRACTOR_STATUS_COLORS: Record<string, BadgeColor> = {
  active: "green",
  suspended: "amber",
  blacklisted: "red",
};

export const CONTRACT_STATUS_COLORS: Record<string, BadgeColor> = {
  draft: "gray",
  active: "blue",
  completed: "green",
  terminated: "red",
};

export const PAYMENT_STATUS_COLORS: Record<string, BadgeColor> = {
  pending: "amber",
  approved: "blue",
  paid: "green",
  rejected: "red",
};

export const PROJECT_STATUS_COLORS: Record<string, BadgeColor> = {
  planning: "gray",
  active: "blue",
  on_hold: "amber",
  completed: "green",
  cancelled: "red",
};
