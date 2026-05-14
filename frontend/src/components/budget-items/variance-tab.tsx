"use client";

import { useEffect, useMemo, useState } from "react";
import {
  RefreshCw,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Search,
  ArrowUp,
  ArrowDown,
  ArrowDownUp,
} from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError } from "@/lib/api-client";
import { formatRubCompact } from "@/lib/formatters";
import { useT } from "@/lib/i18n/provider";
import type {
  BudgetVarianceReport,
  BudgetItemVariance,
  VarianceSeverity,
} from "@/types/budget";

interface Props {
  projectId: number;
}

// Severity styles (color + icon). Labels are localized inside the component
// via t() — keep this map style-only to avoid stale strings.
const SEVERITY_STYLE: Record<
  VarianceSeverity,
  { cls: string; icon: React.ComponentType<{ className?: string }>; tKey: string }
> = {
  ok: {
    cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
    icon: CheckCircle2,
    tKey: "budget.filterOnBudget",
  },
  watch: {
    cls: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30",
    icon: TrendingUp,
    tKey: "budget.filterWatch",
  },
  warn: {
    cls: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30",
    icon: AlertTriangle,
    tKey: "budget.filterNearLimit",
  },
  over: {
    cls: "bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/30",
    icon: AlertTriangle,
    tKey: "budget.filterOverBudget",
  },
};

type SortKey = "cost_code" | "description" | "planned" | "actual" | "variance" | null;
type SortDir = "asc" | "desc";

export function BudgetVarianceTab({ projectId }: Props) {
  const { t } = useT();
  const [report, setReport] = useState<BudgetVarianceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<VarianceSeverity | "all">("all");
  const [sortKey, setSortKey] = useState<SortKey>("variance");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  async function load(force = false) {
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await api.budgetItems.varianceForProject(projectId);
      setReport(data);
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : "Failed to load variance report";
      setError(msg);
      if (force) toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const filtered = useMemo<BudgetItemVariance[]>(() => {
    if (!report) return [];
    let items = report.items;
    if (filter !== "all") items = items.filter((i) => i.severity === filter);
    const q = search.trim().toLowerCase();
    if (q) {
      items = items.filter(
        (i) =>
          i.description.toLowerCase().includes(q) ||
          (i.cost_code || "").toLowerCase().includes(q) ||
          i.category_name.toLowerCase().includes(q)
      );
    }
    if (sortKey) {
      const arr = [...items];
      arr.sort((a, b) => {
        let cmp = 0;
        if (sortKey === "cost_code") {
          cmp = (a.cost_code || "").localeCompare(b.cost_code || "");
        } else if (sortKey === "description") {
          cmp = a.description.localeCompare(b.description);
        } else if (sortKey === "planned") {
          cmp = parseFloat(a.planned_amount) - parseFloat(b.planned_amount);
        } else if (sortKey === "actual") {
          cmp = parseFloat(a.actual_amount) - parseFloat(b.actual_amount);
        } else if (sortKey === "variance") {
          cmp = parseFloat(a.variance) - parseFloat(b.variance);
        }
        return sortDir === "asc" ? cmp : -cmp;
      });
      items = arr;
    }
    return items;
  }, [report, search, filter, sortKey, sortDir]);

  const counts = useMemo(() => {
    const c = { all: 0, ok: 0, watch: 0, warn: 0, over: 0 } as Record<string, number>;
    if (report) {
      c.all = report.items.length;
      for (const i of report.items) c[i.severity] += 1;
    }
    return c;
  }, [report]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          {error || t("budget.noVarianceData")}
          <div className="mt-3">
            <Button size="sm" variant="outline" onClick={() => load(true)}>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              {t("budget.retry")}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const overallSeverity: VarianceSeverity =
    parseFloat(report.overall_variance) > 0
      ? (report.overall_variance_pct ?? 0) > 0
        ? "over"
        : "watch"
      : "ok";
  const totalsCls = SEVERITY_STYLE[overallSeverity].cls;

  return (
    <div className="space-y-4">
      {/* Top KPI strip */}
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-cyan-500/5">
        <CardHeader className="pb-3 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              {t("budget.varianceTitle")}
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              {t("budget.varianceLineCount", { n: report.items.length })} ·{" "}
              {new Date(report.generated_at).toLocaleString("en-GB")}
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={() => load(true)} disabled={refreshing}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`} />
            {t("budget.refresh")}
          </Button>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
            <KpiTile label={t("budget.kpiPlanned")} value={formatRubCompact(report.total_planned)} />
            <KpiTile label={t("budget.kpiCommitted")} value={formatRubCompact(report.total_committed)} />
            <KpiTile label={t("budget.kpiActual")} value={formatRubCompact(report.total_actual)} />
            <KpiTile
              label={t("budget.kpiVariance")}
              value={
                (parseFloat(report.overall_variance) >= 0 ? "+" : "") +
                formatRubCompact(report.overall_variance) +
                (report.overall_variance_pct !== null
                  ? ` (${report.overall_variance_pct.toFixed(1)}%)`
                  : "")
              }
              className={totalsCls}
            />
          </div>
        </CardContent>
      </Card>

      {/* Filter chips + search */}
      <div className="flex flex-wrap items-center gap-2">
        {(["all", "over", "warn", "watch", "ok"] as const).map((s) => {
          const isActive = filter === s;
          const label = s === "all" ? t("budget.filterAll") : t(SEVERITY_STYLE[s].tKey);
          return (
            <button
              key={s}
              type="button"
              onClick={() => setFilter(s)}
              className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                isActive
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-card text-muted-foreground hover:text-foreground"
              }`}
            >
              {label}
              <span className="ml-1.5 opacity-70">({counts[s] ?? 0})</span>
            </button>
          );
        })}
        <div className="flex-1" />
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("budget.searchPlaceholder")}
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Variance table */}
      <Card>
        <CardContent className="pt-6">
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              {t("budget.noMatching")}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[110px]">
                    <SortHeader
                      label={t("budget.colCode")}
                      active={sortKey === "cost_code"}
                      dir={sortDir}
                      onClick={() => handleSort("cost_code")}
                    />
                  </TableHead>
                  <TableHead>
                    <SortHeader
                      label={t("budget.colDescription")}
                      active={sortKey === "description"}
                      dir={sortDir}
                      onClick={() => handleSort("description")}
                    />
                  </TableHead>
                  <TableHead className="w-[120px]">{t("budget.colCategory")}</TableHead>
                  <TableHead className="w-[110px] text-right">
                    <SortHeader
                      label={t("budget.kpiPlanned")}
                      active={sortKey === "planned"}
                      dir={sortDir}
                      onClick={() => handleSort("planned")}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="w-[110px] text-right">{t("budget.colCommitted")}</TableHead>
                  <TableHead className="w-[110px] text-right">
                    <SortHeader
                      label={t("budget.actual")}
                      active={sortKey === "actual"}
                      dir={sortDir}
                      onClick={() => handleSort("actual")}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="w-[120px] text-right">
                    <SortHeader
                      label={t("budget.variance")}
                      active={sortKey === "variance"}
                      dir={sortDir}
                      onClick={() => handleSort("variance")}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="w-[110px]">{t("budget.colStatus")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((it) => {
                  const sev = SEVERITY_STYLE[it.severity];
                  const SevIcon = sev.icon;
                  const sevLabel = t(sev.tKey);
                  const variance = parseFloat(it.variance);
                  return (
                    <TableRow key={it.id}>
                      <TableCell className="font-mono text-xs">
                        {it.cost_code || "—"}
                      </TableCell>
                      <TableCell className="text-sm">
                        <div className="line-clamp-1" title={it.description}>
                          {it.description}
                        </div>
                        {it.matched_expense_count > 0 && (
                          <div className="text-[10px] text-muted-foreground mt-0.5">
                            {t("budget.matchedExpenses", { n: it.matched_expense_count })}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px]">
                          {it.category_name}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">
                        {formatRubCompact(it.planned_amount)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs text-muted-foreground">
                        {formatRubCompact(it.committed_amount)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">
                        {formatRubCompact(it.actual_amount)}
                      </TableCell>
                      <TableCell
                        className={`text-right font-mono text-xs font-medium ${
                          variance > 0
                            ? "text-rose-600 dark:text-rose-400"
                            : variance < 0
                            ? "text-emerald-600 dark:text-emerald-400"
                            : "text-muted-foreground"
                        }`}
                      >
                        {variance > 0 ? "+" : ""}
                        {formatRubCompact(it.variance)}
                        {it.variance_pct !== null && (
                          <span className="text-[10px] block text-muted-foreground">
                            {it.variance_pct.toFixed(1)}%
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={`text-[10px] gap-1 ${sev.cls}`}>
                          <SevIcon className="h-3 w-3" />
                          {sevLabel}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------- Helpers ----------

function KpiTile({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={`rounded-md border bg-card p-3 ${className || ""}`}>
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">
        {label}
      </p>
      <p className="text-base font-bold mt-1 truncate">{value}</p>
    </div>
  );
}

function SortHeader({
  label,
  active,
  dir,
  onClick,
  align = "left",
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
  align?: "left" | "right";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1 hover:text-foreground transition-colors ${
        align === "right" ? "ml-auto" : ""
      } ${active ? "text-foreground font-medium" : "text-muted-foreground"}`}
    >
      {align === "right" && active ? (
        dir === "asc" ? (
          <ArrowUp className="h-3 w-3" />
        ) : (
          <ArrowDown className="h-3 w-3" />
        )
      ) : null}
      <span>{label}</span>
      {align !== "right" ? (
        active ? (
          dir === "asc" ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )
        ) : (
          <ArrowDownUp className="h-3 w-3 opacity-40" />
        )
      ) : null}
    </button>
  );
}
