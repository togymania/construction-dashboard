"use client";

import { useEffect, useState } from "react";
import {
  Building2,
  Users,
  Upload,
  TrendingUp,
  TrendingDown,
  Minus,
  Calendar,
  HardHat,
  Briefcase,
  Activity,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  UserCheck,
  UsersRound,
  Percent,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api-client";
import { useUser } from "@/components/providers/user-provider";
import { useT } from "@/lib/i18n/provider";
import { WorkforceDashboardCharts } from "@/components/workforce/dashboard-charts";
import { WorkforceUploadDialog } from "@/components/workforce/upload-dialog";
import { WorkforceInsightsCard } from "@/components/workforce/insights-card";
import type {
  WorkforceCategory,
  WorkforceKPIBundle,
  WorkforceKPICategoryToday,
  WorkforceKPICompanyToday,
  WorkforceSnapshotListItem,
} from "@/types/workforce";
import { useProject } from "@/components/providers/project-provider";

export default function WorkforcePage() {
  const { user } = useUser();
  const { t } = useT();
  const { project } = useProject();
  const ACTIVE_PROJECT_ID = project?.id ?? 0;
  const canUpload =
    !!user &&
    (user.role === "admin" ||
      user.role === "project_manager" ||
      user.role === "workforce_editor");

  const [kpis, setKpis] = useState<WorkforceKPIBundle | null>(null);
  const [recent, setRecent] = useState<WorkforceSnapshotListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  async function loadAll() {
    setError(null);
    try {
      const [kpiRes, listRes] = await Promise.all([
        api.workforce.kpis(ACTIVE_PROJECT_ID),
        api.workforce.listSnapshots(ACTIVE_PROJECT_ID, { limit: 10 }),
      ]);
      setKpis(kpiRes);
      setRecent(listRes);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load workforce data");
    }
  }

  useEffect(() => {
    if (ACTIVE_PROJECT_ID > 0) {
      loadAll();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ACTIVE_PROJECT_ID]);

  function handleUploadComplete() {
    setUploadOpen(false);
    loadAll();
  }

  // Compute derived KPIs for the top row
  const totalWorkforce = kpis
    ? kpis.by_category_today.reduce((sum, c) => sum + c.present_today, 0)
    : 0;
  const directToday = kpis?.by_category_today.find((c) => c.category === "direct");
  const subcontractorToday = kpis?.by_category_today.find((c) => c.category === "subcontractor");

  // Weekly change %
  let weeklyChangePct: number | null = null;
  let weeklyChangeAbs: number | null = null;
  if (kpis && kpis.weekly_buckets.length >= 2) {
    const last = kpis.weekly_buckets[kpis.weekly_buckets.length - 1];
    const prev = kpis.weekly_buckets[kpis.weekly_buckets.length - 2];
    weeklyChangeAbs = Math.round(last.avg_total_present - prev.avg_total_present);
    weeklyChangePct = prev.avg_total_present > 0
      ? ((last.avg_total_present - prev.avg_total_present) / prev.avg_total_present) * 100
      : null;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-heading flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/10 flex items-center justify-center">
              <Users className="h-5 w-5 text-primary" />
            </div>
            {t("pages.workforce")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1.5 ml-[52px]">
            {t("pages.workforceSubtitle")}
          </p>
        </div>
        {canUpload && (
          <Button onClick={() => setUploadOpen(true)} className="gap-2">
            <Upload className="h-4 w-4" />
            {t("workforce.uploadExcel")}
          </Button>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0" />
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Loading skeletons */}
      {!error && kpis === null && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <Card key={i} className="border-foreground/5 bg-card/60">
              <CardContent className="pt-6 space-y-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-9 w-32" />
                <Skeleton className="h-3 w-20" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Empty state - no snapshots ever */}
      {kpis !== null && kpis.snapshot_count === 0 && (
        <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
          <CardContent className="flex flex-col items-center justify-center py-20 text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 border border-primary/15 flex items-center justify-center">
              <Users className="h-7 w-7 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-heading font-semibold">No workforce data yet</h2>
              <p className="text-sm text-muted-foreground mt-1 max-w-md">
                Upload a daily puantaj Excel file (cover-page format) to see KPIs,
                trends, discipline breakdowns, and AI insights here.
              </p>
            </div>
            {canUpload && (
              <Button onClick={() => setUploadOpen(true)} className="gap-2">
                <Upload className="h-4 w-4" />
                {t("workforce.uploadExcel")}
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* KPI cards + charts (only when there is data) */}
      {kpis !== null && kpis.snapshot_count > 0 && (
        <>
          {/* As of date subtitle */}
          {kpis.as_of_date && (
            <p className="text-xs text-muted-foreground -mt-2 flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" />
              Data as of {kpis.as_of_date}
              {" · "}
              {kpis.snapshot_count} {kpis.snapshot_count === 1 ? "snapshot" : "snapshots"} on file
            </p>
          )}

          {/* 4 KPI cards - Total / Direct / Subcontractor / Weekly Change */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Workforce */}
            <HeroKpiCard
              label="Total Workforce"
              value={totalWorkforce}
              icon={<UsersRound className="h-4 w-4" />}
              tint="oklch(0.65 0.20 270)"
              delta={
                kpis.by_category_today.length > 0
                  ? kpis.by_category_today.reduce((s, c) => s + c.delta_vs_yesterday, 0)
                  : null
              }
              description="All personnel on site today"
            />

            {/* Direct Workforce */}
            <HeroKpiCard
              label="Direct Workforce"
              value={directToday?.present_today ?? 0}
              icon={<HardHat className="h-4 w-4" />}
              tint="oklch(0.62 0.20 270)"
              delta={directToday?.delta_vs_yesterday ?? null}
              deltaPct={directToday?.delta_pct ?? null}
              description={`${directToday?.position_count ?? 0} positions`}
            />

            {/* Subcontractor Workforce */}
            <HeroKpiCard
              label="Subcontractor"
              value={subcontractorToday?.present_today ?? 0}
              icon={<Activity className="h-4 w-4" />}
              tint="oklch(0.68 0.18 155)"
              delta={subcontractorToday?.delta_vs_yesterday ?? null}
              deltaPct={subcontractorToday?.delta_pct ?? null}
              description={`${subcontractorToday?.position_count ?? 0} positions`}
            />

            {/* Weekly Change % */}
            <HeroKpiCard
              label="Weekly Change"
              value={weeklyChangePct !== null ? `${weeklyChangePct > 0 ? "+" : ""}${weeklyChangePct.toFixed(1)}%` : "—"}
              icon={<Percent className="h-4 w-4" />}
              tint="oklch(0.75 0.18 65)"
              delta={weeklyChangeAbs}
              description="This week vs last week avg"
              isPercentage
            />
          </div>

          {/* Per-company breakdown */}
          {kpis.by_company_today.length > 0 && (
            <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  Today by Company
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {kpis.by_company_today.map((c) => (
                    <CompanyBreakdownCard key={c.company_label} company={c} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Main content: Charts + AI Insights sidebar */}
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-6">
            {/* Charts (left/main area) */}
            <WorkforceDashboardCharts kpis={kpis} />

            {/* AI Insights sidebar (right) */}
            <div className="space-y-6">
              <WorkforceInsightsCard insights={kpis.insights ?? null} />
            </div>
          </div>

          {/* Recent snapshots table */}
          {recent !== null && recent.length > 0 && (
            <RecentSnapshotsTable snapshots={recent} />
          )}
        </>
      )}

      {/* Upload dialog */}
      {canUpload && (
        <WorkforceUploadDialog
          projectId={ACTIVE_PROJECT_ID}
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          onComplete={handleUploadComplete}
        />
      )}
    </div>
  );
}

// =============================================================================
// HeroKpiCard - premium KPI card with glassmorphism
// =============================================================================
function HeroKpiCard({
  label,
  value,
  icon,
  tint,
  delta,
  deltaPct,
  description,
  isPercentage,
}: {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  tint: string;
  delta?: number | null;
  deltaPct?: number | null;
  description?: string;
  isPercentage?: boolean;
}) {
  const hasDelta = delta !== null && delta !== undefined;
  const isUp = hasDelta && delta > 0;
  const isDown = hasDelta && delta < 0;

  return (
    <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm hover:bg-card/80 transition-colors group relative overflow-hidden">
      {/* Accent glow */}
      <div
        className="absolute top-0 right-0 w-24 h-24 rounded-full opacity-[0.06] blur-2xl pointer-events-none"
        style={{ backgroundColor: tint }}
      />
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {label}
          </CardTitle>
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center"
            style={{
              backgroundColor: `color-mix(in oklch, ${tint} 12%, transparent)`,
              color: tint,
            }}
          >
            {icon}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="text-3xl font-bold tracking-tight tabular-nums font-heading">
          {typeof value === "number" ? value.toLocaleString() : value}
        </div>
        <div className="flex items-center gap-2 text-xs">
          {hasDelta && !isPercentage && (
            <span
              className={
                "flex items-center gap-0.5 tabular-nums font-medium " +
                (isUp ? "text-emerald-500" : isDown ? "text-amber-500" : "text-muted-foreground")
              }
            >
              {isUp ? (
                <ArrowUpRight className="h-3.5 w-3.5" />
              ) : isDown ? (
                <ArrowDownRight className="h-3.5 w-3.5" />
              ) : (
                <Minus className="h-3.5 w-3.5" />
              )}
              {delta === 0
                ? "no change"
                : (delta > 0 ? "+" : "") +
                  delta +
                  (deltaPct != null ? ` (${deltaPct.toFixed(1)}%)` : "")}
              <span className="text-muted-foreground ml-1">vs prev</span>
            </span>
          )}
          {hasDelta && isPercentage && (
            <span
              className={
                "flex items-center gap-0.5 tabular-nums font-medium " +
                (isUp ? "text-emerald-500" : isDown ? "text-amber-500" : "text-muted-foreground")
              }
            >
              {isUp ? (
                <ArrowUpRight className="h-3.5 w-3.5" />
              ) : isDown ? (
                <ArrowDownRight className="h-3.5 w-3.5" />
              ) : (
                <Minus className="h-3.5 w-3.5" />
              )}
              {(delta > 0 ? "+" : "") + delta} avg headcount
            </span>
          )}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// CompanyBreakdownCard - one card per company showing 3 categories
// =============================================================================
const COMPANY_TINT: Record<string, string> = {
  Monotekstroy: "oklch(0.62 0.20 270)",  // indigo
  Monart: "oklch(0.68 0.18 155)",        // emerald
};

// Backend company_label → display string. "Monart" → "Monart Stroy",
// "Monotekstroy" → "Monotek Stroy". Tutarlı görsel branding için.
function displayCompany(label: string | null | undefined): string {
  if (!label) return "";
  const norm = label.trim();
  if (norm === "Monart") return "Monart Stroy";
  if (norm.toLowerCase() === "monotekstroy") return "Monotek Stroy";
  if (norm === "Monotek") return "Monotek Stroy";
  return norm;
}

function CompanyBreakdownCard({ company }: { company: WorkforceKPICompanyToday }) {
  const tint = COMPANY_TINT[company.company_label] ?? "oklch(0.62 0.20 270)";
  return (
    <div
      className="rounded-xl border bg-card/40 p-4 space-y-3 hover:bg-card/60 transition-colors"
      style={{ borderColor: `color-mix(in oklch, ${tint} 30%, transparent)` }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: tint }}
          />
          <span className="font-heading font-semibold tracking-tight">
            {displayCompany(company.company_label)}
          </span>
        </div>
        <span className="text-xs text-muted-foreground tabular-nums">
          total {company.total_present}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <CompanyStatBox label="Direct" value={company.direct_present} accentTint="oklch(0.62 0.20 270)" />
        <CompanyStatBox label="Indirect" value={company.indirect_present} accentTint="oklch(0.70 0.15 200)" />
        <CompanyStatBox label="Subcont." value={company.subcontractor_present} accentTint="oklch(0.68 0.18 155)" />
      </div>
    </div>
  );
}

function CompanyStatBox({
  label,
  value,
  accentTint,
}: {
  label: string;
  value: number;
  accentTint: string;
}) {
  return (
    <div className="rounded-md bg-card/60 border border-foreground/8 px-2 py-2 text-center">
      <div
        className="text-2xl font-heading font-bold tabular-nums"
        style={{ color: accentTint }}
      >
        {value}
      </div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider mt-0.5">
        {label}
      </div>
    </div>
  );
}

// =============================================================================
// RecentSnapshotsTable - premium sortable table (Phase 6)
// =============================================================================
function RecentSnapshotsTable({ snapshots }: { snapshots: WorkforceSnapshotListItem[] }) {
  const [sortKey, setSortKey] = useState<"date" | "company" | "total">("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sorted = [...snapshots].sort((a, b) => {
    let cmp = 0;
    switch (sortKey) {
      case "date":
        cmp = a.snapshot_date.localeCompare(b.snapshot_date);
        break;
      case "company":
        cmp = a.company_label.localeCompare(b.company_label);
        break;
      case "total":
        cmp = a.total_present - b.total_present;
        break;
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  // Compute delta vs prev day per snapshot (rough approximation)
  const deltaMap = new Map<number, number>();
  const byDateCompany = new Map<string, WorkforceSnapshotListItem[]>();
  for (const s of snapshots) {
    const key = s.company_label;
    if (!byDateCompany.has(key)) byDateCompany.set(key, []);
    byDateCompany.get(key)!.push(s);
  }
  for (const [, companySnaps] of byDateCompany) {
    const sortedByDate = [...companySnaps].sort((a, b) =>
      a.snapshot_date.localeCompare(b.snapshot_date)
    );
    for (let i = 1; i < sortedByDate.length; i++) {
      deltaMap.set(
        sortedByDate[i].id,
        sortedByDate[i].total_present - sortedByDate[i - 1].total_present
      );
    }
  }

  const SortHeader = ({
    children,
    sortId,
    className,
  }: {
    children: React.ReactNode;
    sortId: typeof sortKey;
    className?: string;
  }) => (
    <th
      className={
        "px-3 py-2.5 text-left text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none hover:text-foreground transition-colors " +
        (sortKey === sortId ? "text-foreground" : "text-muted-foreground") +
        (className ? " " + className : "")
      }
      onClick={() => toggleSort(sortId)}
    >
      <span className="flex items-center gap-1">
        {children}
        {sortKey === sortId && (
          <span className="text-primary">{sortDir === "asc" ? "↑" : "↓"}</span>
        )}
      </span>
    </th>
  );

  return (
    <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-base font-medium">Recent Snapshots</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-foreground/5">
              <tr>
                <SortHeader sortId="date">Date</SortHeader>
                <SortHeader sortId="company">Company</SortHeader>
                <th className="px-3 py-2.5 text-left text-[10px] uppercase tracking-wider font-medium text-muted-foreground">Direct</th>
                <th className="px-3 py-2.5 text-left text-[10px] uppercase tracking-wider font-medium text-muted-foreground">Subcont.</th>
                <SortHeader sortId="total">Total</SortHeader>
                <th className="px-3 py-2.5 text-left text-[10px] uppercase tracking-wider font-medium text-muted-foreground">Δ Prev</th>
                <th className="px-3 py-2.5 text-left text-[10px] uppercase tracking-wider font-medium text-muted-foreground">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-foreground/5">
              {sorted.map((s) => {
                const delta = deltaMap.get(s.id);
                return (
                  <tr
                    key={s.id}
                    className="hover:bg-muted/20 transition-colors"
                  >
                    <td className="px-3 py-3 font-medium tabular-nums whitespace-nowrap">
                      {s.snapshot_date}
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={
                          "text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border " +
                          (s.company_label === "Monotekstroy"
                            ? "border-[oklch(0.62_0.20_270)]/30 bg-[oklch(0.62_0.20_270)]/10 text-[oklch(0.62_0.20_270)]"
                            : "border-[oklch(0.68_0.18_155)]/30 bg-[oklch(0.68_0.18_155)]/10 text-[oklch(0.68_0.18_155)]")
                        }
                      >
                        {displayCompany(s.company_label)}
                      </span>
                    </td>
                    <td className="px-3 py-3 tabular-nums text-muted-foreground">
                      {s.direct_present}
                    </td>
                    <td className="px-3 py-3 tabular-nums text-muted-foreground">
                      {s.subcontractor_present}
                    </td>
                    <td className="px-3 py-3 font-heading font-semibold tabular-nums">
                      {s.total_present}
                    </td>
                    <td className="px-3 py-3 tabular-nums">
                      {delta !== undefined ? (
                        <span
                          className={
                            "inline-flex items-center gap-0.5 text-xs font-medium " +
                            (delta > 0
                              ? "text-emerald-500"
                              : delta < 0
                              ? "text-amber-500"
                              : "text-muted-foreground")
                          }
                        >
                          {delta > 0 ? "+" : ""}
                          {delta}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 text-emerald-500">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        Imported
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
