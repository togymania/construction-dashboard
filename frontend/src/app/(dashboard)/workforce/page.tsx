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
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api-client";
import { useUser } from "@/components/providers/user-provider";
import { WorkforceDashboardCharts } from "@/components/workforce/dashboard-charts";
import { WorkforceUploadDialog } from "@/components/workforce/upload-dialog";
import type {
  WorkforceCategory,
  WorkforceKPIBundle,
  WorkforceKPICategoryToday,
  WorkforceKPICompanyToday,
  WorkforceSnapshotListItem,
} from "@/types/workforce";

// Hard-coded for now (single project assumption from Day 10 plan).
// When multi-project lands, this becomes a project picker.
const ACTIVE_PROJECT_ID = 1;

export default function WorkforcePage() {
  const { user } = useUser();
  const canUpload = user && (user.role === "admin" || user.role === "project_manager");

  const [kpis, setKpis] = useState<WorkforceKPIBundle | null>(null);
  const [recent, setRecent] = useState<WorkforceSnapshotListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  async function loadAll() {
    setError(null);
    try {
      const [kpiRes, listRes] = await Promise.all([
        api.workforce.kpis(ACTIVE_PROJECT_ID),
        api.workforce.listSnapshots(ACTIVE_PROJECT_ID, { limit: 5 }),
      ]);
      setKpis(kpiRes);
      setRecent(listRes);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load workforce data");
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  function handleUploadComplete() {
    setUploadOpen(false);
    loadAll();
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight font-heading flex items-center gap-3">
            <Users className="h-7 w-7 text-primary" />
            Workforce
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Daily personnel snapshot - direct, indirect, and subcontractor counts.
          </p>
        </div>
        {canUpload && (
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Upload Excel
          </Button>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <Card className="border-destructive/50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0" />
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Loading skeletons */}
      {!error && kpis === null && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
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
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
              <Users className="h-7 w-7 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-heading font-semibold">No workforce data yet</h2>
              <p className="text-sm text-muted-foreground mt-1 max-w-md">
                Upload a daily puantaj Excel file (cover-page format) to see KPIs and trends here.
              </p>
            </div>
            {canUpload && (
              <Button onClick={() => setUploadOpen(true)}>
                <Upload className="h-4 w-4 mr-2" />
                Upload Excel
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

          {/* 3 KPI cards (project-wide totals: Mono + Monart) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {kpis.by_category_today.map((c) => (
              <CategoryKpiCard key={c.category} card={c} />
            ))}
          </div>

          {/* Per-company breakdown */}
          {kpis.by_company_today.length > 0 && (
            <Card>
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

          {/* Charts (4 subcomponents inside) */}
          <WorkforceDashboardCharts kpis={kpis} />

          {/* Recent uploads */}
          {recent !== null && recent.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-medium">Recent Snapshots</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="divide-y divide-border/40">
                  {recent.map((s) => (
                    <li key={s.id} className="py-3 flex items-center gap-4 text-sm">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium tabular-nums">{s.snapshot_date}</span>
                          <span className={
                            "text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border " +
                            (s.company_label === "Monotekstroy"
                              ? "border-[oklch(0.62_0.20_270)]/30 bg-[oklch(0.62_0.20_270)]/10 text-[oklch(0.62_0.20_270)]"
                              : "border-[oklch(0.68_0.18_155)]/30 bg-[oklch(0.68_0.18_155)]/10 text-[oklch(0.68_0.18_155)]")
                          }>
                            {s.company_label}
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground truncate mt-0.5">
                          {s.source}
                          {s.source_filename ? " · " + s.source_filename : ""}
                          {s.uploaded_by_user ? " · " + s.uploaded_by_user.full_name : ""}
                        </div>
                      </div>
                      <div className="text-right tabular-nums">
                        <div className="font-heading font-semibold">{s.total_present}</div>
                        <div className="text-[10px] text-muted-foreground uppercase tracking-wider">present</div>
                      </div>
                      <div className="hidden sm:flex gap-3 text-xs text-muted-foreground tabular-nums">
                        <span>D {s.direct_present}</span>
                        <span>I {s.indirect_present}</span>
                        <span>S {s.subcontractor_present}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
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
// CategoryKpiCard - one of the three big cards at the top
// =============================================================================
const CATEGORY_META: Record<
  WorkforceCategory,
  { label: string; description: string; Icon: typeof HardHat; tint: string }
> = {
  direct: {
    label: "Direct",
    description: "Productive personnel on site",
    Icon: HardHat,
    tint: "text-[oklch(0.62_0.20_270)]",
  },
  indirect: {
    label: "Indirect",
    description: "Engineers and office staff",
    Icon: Briefcase,
    tint: "text-[oklch(0.70_0.15_200)]",
  },
  subcontractor: {
    label: "Subcontractor",
    description: "Third-party crews",
    Icon: Activity,
    tint: "text-[oklch(0.68_0.18_155)]",
  },
};

function CategoryKpiCard({ card }: { card: WorkforceKPICategoryToday }) {
  const meta = CATEGORY_META[card.category];
  const Icon = meta.Icon;

  // Delta direction
  const isUp = card.delta_vs_yesterday > 0;
  const isDown = card.delta_vs_yesterday < 0;
  const isFlat = card.delta_vs_yesterday === 0;

  let deltaIcon = Minus;
  let deltaColor = "text-muted-foreground";
  if (isUp) {
    deltaIcon = TrendingUp;
    deltaColor = "text-emerald-500";
  } else if (isDown) {
    deltaIcon = TrendingDown;
    deltaColor = "text-amber-500";
  }
  const DeltaIcon = deltaIcon;

  // Hide delta on first day (delta_pct null AND no yesterday data)
  const showDelta = card.delta_pct !== null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {meta.label}
          </CardTitle>
          <Icon className={"h-4 w-4 " + meta.tint} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="text-3xl font-bold tracking-tight tabular-nums font-heading">
          {card.present_today}
        </div>
        <div className="flex items-center gap-2 text-xs">
          {showDelta ? (
            <span className={"flex items-center gap-1 tabular-nums " + deltaColor}>
              <DeltaIcon className="h-3.5 w-3.5" />
              {isFlat
                ? "no change"
                : (card.delta_vs_yesterday > 0 ? "+" : "") +
                  card.delta_vs_yesterday +
                  (card.delta_pct !== null ? " (" + card.delta_pct.toFixed(1) + "%)" : "")}
              <span className="text-muted-foreground">vs yesterday</span>
            </span>
          ) : (
            <span className="text-muted-foreground">First snapshot</span>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {card.position_count} {card.position_count === 1 ? "position" : "positions"} · {meta.description}
        </p>
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

function CompanyBreakdownCard({ company }: { company: WorkforceKPICompanyToday }) {
  const tint = COMPANY_TINT[company.company_label] ?? "oklch(0.62 0.20 270)";
  return (
    <div
      className="rounded-xl border bg-card/40 p-4 space-y-3"
      style={{ borderColor: `color-mix(in oklch, ${tint} 30%, transparent)` }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: tint }}
          />
          <span className="font-heading font-semibold tracking-tight">
            {company.company_label}
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

