/**
 * Format a numeric or string RUB amount as full number with thousands separator.
 * Example: "1,480,000,000 ₽"
 */
export function formatRub(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "0 ₽";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "0 ₽";
  return `${Math.round(num).toLocaleString("en-US")} ₽`;
}

/**
 * Compact format for narrow spaces. Example: "1.48B ₽" or "245.3M ₽".
 */
export function formatRubCompact(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "0 ₽";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "0 ₽";

  if (num >= 1_000_000_000) return `${(num / 1_000_000_000).toFixed(2)}B ₽`;
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M ₽`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K ₽`;
  return `${Math.round(num)} ₽`;
}

/**
 * Backward-compatible alias for code that still calls formatCurrency.
 * Now formats as RUB instead of USD.
 */
export const formatCurrency = formatRub;

/**
 * Format an ISO date (e.g. "2024-03-15") as "Mar 15, 2024".
 */
export function formatDate(isoDate: string | null | undefined): string {
  if (!isoDate) return "-";
  try {
    return new Date(isoDate).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return isoDate;
  }
}

/**
 * Format a percentage string/number as "41.5%".
 */
export function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "0%";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "0%";
  return `${num.toFixed(1)}%`;
}

/**
 * Format a snake_case role or status as "Title Case".
 */
export function formatLabel(value: string): string {
  return value
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
