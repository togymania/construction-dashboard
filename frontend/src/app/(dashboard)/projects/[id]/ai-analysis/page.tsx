"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Sparkles,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  XCircle,
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
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api-client";
import { useT } from "@/lib/i18n/provider";
import type {
  ProjectAIAnalysis,
  KPIStatus,
  KPIStatusLevel,
  VerdictLevel,
  DataConfidence,
} from "@/types/project";

// ---------------------------------------------------------------------------
// Visual helpers
// ---------------------------------------------------------------------------

function verdictTone(v: VerdictLevel): string {
  switch (v) {
    case "ON_TRACK":
      return "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:border-emerald-900";
    case "AT_RISK":
      return "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-900";
    case "CRITICAL":
      return "bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-950/40 dark:text-rose-200 dark:border-rose-900";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/40 dark:text-slate-300 dark:border-slate-700";
  }
}

function statusDotClass(s: KPIStatusLevel): string {
  switch (s) {
    case "ok":
      return "bg-emerald-500";
    case "watch":
      return "bg-amber-500";
    case "critical":
      return "bg-rose-500";
    default:
      return "bg-slate-300 dark:bg-slate-600";
  }
}

function statusTextClass(s: KPIStatusLevel): string {
  switch (s) {
    case "ok":
      return "text-emerald-700 dark:text-emerald-300";
    case "watch":
      return "text-amber-700 dark:text-amber-300";
    case "critical":
      return "text-rose-700 dark:text-rose-300";
    default:
      return "text-muted-foreground";
  }
}

function confidenceTone(c: DataConfidence): string {
  switch (c) {
    case "HIGH":
      return "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300";
    case "MEDIUM":
      return "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300";
    default:
      return "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300";
  }
}

function VerdictIcon({ v }: { v: VerdictLevel }) {
  const cls = "h-7 w-7 shrink-0";
  if (v === "ON_TRACK") return <CheckCircle2 className={cls + " text-emerald-600"} />;
  if (v === "AT_RISK") return <AlertTriangle className={cls + " text-amber-600"} />;
  if (v === "CRITICAL") return <XCircle className={cls + " text-rose-600"} />;
  return <AlertCircle className={cls + " text-slate-500"} />;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ProjectAIAnalysisPage() {
  const params = useParams<{ id: string }>();
  const projectId = parseInt(params.id, 10);
  const { t, locale } = useT();

  const [analysis, setAnalysis] = useState<ProjectAIAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(force = false) {
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await api.projects.aiAnalysis(projectId, force);
      setAnalysis(data);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : t("aiV2.errorLoad");
      setError(msg);
      if (force) toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (projectId > 0) load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, locale]);

  return (
    <div className="space-y-6">
      <PageHeader
        source={analysis?.source}
        generatedAt={analysis?.generated_at}
        onRefresh={() => load(true)}
        refreshing={refreshing}
      />

      {loading && !analysis ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorCard message={error} onRetry={() => load(false)} />
      ) : analysis ? (
        <>
          <VerdictHero v={analysis.verdict} />
          <DriversRow v={analysis.verdict} />
          <ConfidenceActions v={analysis.verdict} />
          <KPIGrid kpis={analysis.kpis} />
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function PageHeader({
  source,
  generatedAt,
  onRefresh,
  refreshing,
}: {
  source: "llm" | "rule" | undefined;
  generatedAt: string | undefined;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const { t } = useT();
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 p-2 text-white shadow-sm">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("aiV2.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("aiV2.subtitle")}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {source ? (
          <Badge variant={source === "llm" ? "default" : "secondary"}>
            {source === "llm" ? "AI" : t("aiV2.ruleBased")}
          </Badge>
        ) : null}
        {generatedAt ? (
          <span className="text-xs text-muted-foreground">
            {new Date(generatedAt).toLocaleString()}
          </span>
        ) : null}
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <RefreshCw
            className={"mr-2 h-4 w-4 " + (refreshing ? "animate-spin" : "")}
          />
          {refreshing ? t("aiV2.working") : t("aiV2.refresh")}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Verdict hero
// ---------------------------------------------------------------------------

function VerdictHero({ v }: { v: ProjectAIAnalysis["verdict"] }) {
  const { t } = useT();
  const tone = verdictTone(v.verdict);
  const verdictLabel = t(
    "aiV2.verdict." + v.verdict
  ) || v.verdict;

  return (
    <Card className={"border-2 " + tone}>
      <CardContent className="flex items-start gap-4 p-6">
        <VerdictIcon v={v.verdict} />
        <div className="space-y-1">
          <div className="text-xs font-medium uppercase tracking-wider opacity-70">
            {t("aiV2.verdictLabel")}
          </div>
          <div className="text-3xl font-bold tracking-tight">
            {verdictLabel}
          </div>
          {v.headline ? (
            <p className="text-sm leading-relaxed opacity-90">{v.headline}</p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Drivers / Blocker / Impact row
// ---------------------------------------------------------------------------

function DriversRow({ v }: { v: ProjectAIAnalysis["verdict"] }) {
  const { t } = useT();
  const impactType = v.impact_summary
    ? t("aiV2.impactType." + v.impact_summary) || v.impact_summary
    : "—";

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {t("aiV2.keyDrivers")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {v.key_drivers.length > 0 ? (
            <ul className="space-y-1.5 text-sm">
              {v.key_drivers.map((d, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-muted-foreground">•</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">—</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {t("aiV2.criticalBlocker")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <p className="text-sm leading-relaxed">
            {v.critical_blocker || (
              <span className="text-muted-foreground">
                {t("aiV2.noBlocker")}
              </span>
            )}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {t("aiV2.impact")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0 space-y-2">
          <div>
            <div className="text-xs text-muted-foreground">
              {t("aiV2.delayDays")}
            </div>
            <div className="text-2xl font-semibold">
              {v.impact_delay_days > 0 ? "+" : ""}
              {v.impact_delay_days}{" "}
              <span className="text-sm font-normal text-muted-foreground">
                {t("aiV2.days")}
              </span>
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">
              {t("aiV2.riskType")}
            </div>
            <div className="text-sm font-medium capitalize">{impactType}</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confidence + Actions row
// ---------------------------------------------------------------------------

function ConfidenceActions({ v }: { v: ProjectAIAnalysis["verdict"] }) {
  const { t } = useT();
  const tone = confidenceTone(v.data_confidence);
  const confLabel = t("aiV2.confidence." + v.data_confidence) || v.data_confidence;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {t("aiV2.dataConfidence")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0 space-y-2">
          <Badge variant="outline" className={tone}>
            {confLabel}
          </Badge>
          {v.data_confidence_note ? (
            <p className="text-sm leading-relaxed text-muted-foreground">
              {v.data_confidence_note}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {t("aiV2.requiredActions")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {v.required_actions.length > 0 ? (
            <ol className="space-y-1.5 text-sm">
              {v.required_actions.map((a, i) => (
                <li key={i} className="flex gap-2">
                  <span className="font-semibold text-muted-foreground">
                    {i + 1}.
                  </span>
                  <span>{a}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-muted-foreground">—</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI grid (8 tiles)
// ---------------------------------------------------------------------------

function KPIGrid({ kpis }: { kpis: KPIStatus[] }) {
  const { t } = useT();
  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {t("aiV2.kpiHeading")}
      </h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {kpis.map((k) => (
          <KPITile key={k.key} kpi={k} />
        ))}
      </div>
    </div>
  );
}

function KPITile({ kpi }: { kpi: KPIStatus }) {
  const { t } = useT();
  const label = t("aiV2.kpi." + kpi.key) || kpi.label || kpi.key;
  return (
    <Card>
      <CardContent className="space-y-1.5 p-4">
        <div className="flex items-center gap-2">
          <span className={"h-2 w-2 rounded-full " + statusDotClass(kpi.status)} />
          <span className="text-xs font-medium text-muted-foreground line-clamp-1">
            {label}
          </span>
        </div>
        <div
          className={
            "text-xl font-semibold tabular-nums " + statusTextClass(kpi.status)
          }
        >
          {kpi.value || "—"}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Loading + error
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-28 w-full" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    </div>
  );
}

function ErrorCard({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  const { t } = useT();
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 p-8 text-center">
        <AlertCircle className="h-8 w-8 text-rose-500" />
        <div>
          <div className="font-medium">{t("aiV2.loadFailed")}</div>
          <div className="text-sm text-muted-foreground">{message}</div>
        </div>
        <Button onClick={onRetry} variant="outline" size="sm">
          {t("aiV2.tryAgain")}
        </Button>
      </CardContent>
    </Card>
  );
}
