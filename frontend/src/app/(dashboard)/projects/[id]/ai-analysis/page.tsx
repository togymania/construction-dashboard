"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Sparkles,
  RefreshCw,
  CalendarClock,
  Database,
  Wallet,
  Users,
  ShieldAlert,
  Brain,
  AlertCircle,
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
import { formatRubCompact } from "@/lib/formatters";
import type { ProjectAIAnalysis } from "@/types/project";

// ---------------------------------------------------------------------------
// Small typed helpers used by all six cards
// ---------------------------------------------------------------------------

type StatusTone = "good" | "warning" | "critical" | "neutral";

function toneClass(tone: StatusTone): string {
  switch (tone) {
    case "good":
      return "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900";
    case "warning":
      return "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900";
    case "critical":
      return "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/40 dark:text-slate-300 dark:border-slate-700";
  }
}

function riskTone(level: "LOW" | "MEDIUM" | "HIGH"): StatusTone {
  if (level === "HIGH") return "critical";
  if (level === "MEDIUM") return "warning";
  return "good";
}

function financialTone(status: string): StatusTone {
  if (status === "OVER_BUDGET") return "critical";
  if (status === "UNDER_BUDGET") return "good";
  if (status === "ON_TRACK") return "good";
  return "neutral";
}

function executiveTone(status: string): StatusTone {
  if (status === "CRITICAL") return "critical";
  if (status === "WARNING") return "warning";
  if (status === "GOOD") return "good";
  return "neutral";
}

function fmtMoney(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  return formatRubCompact(n);
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
      const msg =
        e instanceof ApiError ? e.message : t("aiAnalysis.errorLoad");
      setError(msg);
      if (force) toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (projectId > 0) load(false);
    // Re-load when the UI language flips so the X-User-Lang header
    // change is reflected in a fresh narrative.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, locale]);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("aiAnalysis.title") || "AI Project Analysis"}
        subtitle={
          t("aiAnalysis.subtitle") ||
          "Schedule, finance, risk and productivity synthesized by AI"
        }
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
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <ScheduleCard a={analysis} />
          <DataQualityCard a={analysis} />
          <FinancialCard a={analysis} />
          <ProductivityCard a={analysis} />
          <RiskCard a={analysis} />
          <ExecutiveCard a={analysis} className="md:col-span-2 xl:col-span-3" />
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page header (title + refresh + source badge)
// ---------------------------------------------------------------------------

function PageHeader({
  title,
  subtitle,
  source,
  generatedAt,
  onRefresh,
  refreshing,
}: {
  title: string;
  subtitle: string;
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
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {source ? (
          <Badge variant={source === "llm" ? "default" : "secondary"}>
            {source === "llm" ? "AI" : t("aiAnalysis.ruleBased")}
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
          {refreshing ? t("aiAnalysis.working") : t("aiAnalysis.refresh")}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cards
// ---------------------------------------------------------------------------

function ScheduleCard({ a }: { a: ProjectAIAnalysis }) {
  const { t } = useT();
  const s = a.schedule;
  const tone: StatusTone = s.delayed_contracts === 0 ? "good" : "critical";
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-rose-500">🔴</span>
          <CalendarClock className="h-4 w-4" />
          {t("aiAnalysis.cardSchedule")}
        </CardTitle>
        <Badge variant="outline" className={toneClass(tone)}>
          {s.delayed_contracts}/{s.total_contracts} {t("aiAnalysis.delayed")}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">{t("aiAnalysis.totalDelay")}</span>
          <span className="font-medium">{s.total_delay_days} {t("aiAnalysis.days")}</span>
        </div>
        {s.critical_delays.length > 0 ? (
          <div>
            <div className="mb-1 text-xs font-medium text-muted-foreground">
              {t("aiAnalysis.critical")}
            </div>
            <ul className="space-y-1">
              {s.critical_delays.slice(0, 4).map((d, i) => (
                <li key={i} className="flex items-start gap-2 text-xs">
                  <span className="mt-[2px] font-mono text-rose-600">
                    +{d.days}d
                  </span>
                  <div>
                    <div className="font-medium">{d.subcontractor}</div>
                    {d.reason ? (
                      <div className="text-muted-foreground">{d.reason}</div>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {s.discipline_delays.length > 0 ? (
          <div>
            <div className="mb-1 text-xs font-medium text-muted-foreground">
              {t("aiAnalysis.byDiscipline")}
            </div>
            <div className="flex flex-wrap gap-1">
              {s.discipline_delays.map((d, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {d.discipline}: {d.delayed_count} ({d.delay_days}d)
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function DataQualityCard({ a }: { a: ProjectAIAnalysis }) {
  const { t } = useT();
  const dq = a.data_quality;
  const tone = riskTone(dq.risk_level);
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-amber-500">🟠</span>
          <Database className="h-4 w-4" />
          {t("aiAnalysis.cardDataQuality")}
        </CardTitle>
        <Badge variant="outline" className={toneClass(tone)}>
          {dq.risk_level}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-md border bg-card p-2">
            <div className="text-xs text-muted-foreground">{t("aiAnalysis.uncategorized")}</div>
            <div className="text-xl font-semibold">{dq.uncategorized_count}</div>
          </div>
          <div className="rounded-md border bg-card p-2">
            <div className="text-xs text-muted-foreground">{t("aiAnalysis.unassigned")}</div>
            <div className="text-xl font-semibold">{dq.unassigned_count}</div>
          </div>
        </div>
        {dq.suggested_matches.length > 0 ? (
          <div>
            <div className="mb-1 text-xs font-medium text-muted-foreground">
              {t("aiAnalysis.suggestedMatches")}
            </div>
            <ul className="space-y-1">
              {dq.suggested_matches.slice(0, 4).map((m, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between rounded border bg-card px-2 py-1 text-xs"
                >
                  <span className="truncate" title={m.description}>
                    {m.description.slice(0, 40)}
                    {m.description.length > 40 ? "…" : ""}
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="font-medium">{m.suggested_target}</span>
                    <Badge variant="secondary" className="text-[10px]">
                      {Math.round(m.confidence * 100)}%
                    </Badge>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function FinancialCard({ a }: { a: ProjectAIAnalysis }) {
  const { t } = useT();
  const f = a.financial;
  const tone = financialTone(f.status);
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-yellow-500">🟡</span>
          <Wallet className="h-4 w-4" />
          {t("aiAnalysis.cardFinancial")}
        </CardTitle>
        <Badge variant="outline" className={toneClass(tone)}>
          {f.status.replace("_", " ")}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Row label={t("aiAnalysis.progressLbl")} value={`${f.progress_pct.toFixed(0)}%`} />
        <Row label={t("aiAnalysis.budgetUsed")} value={`${f.budget_used_pct.toFixed(0)}%`} />
        <Row label={t("aiAnalysis.bacPlan")} value={fmtMoney(f.bac)} />
        <Row label={t("aiAnalysis.acSpent")} value={fmtMoney(f.ac)} />
        <Row
          label={t("aiAnalysis.eacForecast")}
          value={fmtMoney(f.eac)}
          strong
        />
        <Row
          label={t("aiAnalysis.varianceLbl")}
          value={fmtMoney(f.variance)}
          tone={
            parseFloat(String(f.variance)) < 0 ? "critical" : "good"
          }
        />
      </CardContent>
    </Card>
  );
}

function ProductivityCard({ a }: { a: ProjectAIAnalysis }) {
  const { t } = useT();
  const p = a.productivity;
  const tone: StatusTone =
    p.status === "GOOD"
      ? "good"
      : p.status === "LOW"
        ? "critical"
        : p.status === "AVERAGE"
          ? "warning"
          : "neutral";
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-emerald-500">🟢</span>
          <Users className="h-4 w-4" />
          {t("aiAnalysis.cardProductivity")}
        </CardTitle>
        <Badge variant="outline" className={toneClass(tone)}>
          {p.status}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Row label={t("aiAnalysis.headcountLbl")} value={String(p.headcount)} />
        <Row label={t("aiAnalysis.manHours")} value={p.man_hours.toFixed(0)} />
        <Row
          label={t("aiAnalysis.productivityLbl")}
          value={p.productivity != null ? p.productivity.toFixed(2) : "—"}
        />
        <Row
          label={t("aiAnalysis.deviation")}
          value={
            p.deviation_pct != null ? `${p.deviation_pct.toFixed(1)}%` : "—"
          }
        />
      </CardContent>
    </Card>
  );
}

function RiskCard({ a }: { a: ProjectAIAnalysis }) {
  const { t } = useT();
  const r = a.risk;
  const tone = riskTone(r.overall_risk);
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-sky-500">🔵</span>
          <ShieldAlert className="h-4 w-4" />
          {t("aiAnalysis.cardRisk")}
        </CardTitle>
        <Badge variant="outline" className={toneClass(tone)}>
          {r.overall_risk}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Row
          label={t("aiAnalysis.predictedDelay")}
          value={`+${r.predicted_delay_days} ${t("aiAnalysis.days")}`}
        />
        {r.top_risks.length > 0 ? (
          <ol className="space-y-2">
            {r.top_risks.map((risk, i) => (
              <li
                key={i}
                className="rounded-md border bg-card p-2 text-xs"
              >
                <div className="font-medium">{i + 1}. {risk.title}</div>
                {risk.impact ? (
                  <div className="text-muted-foreground">
                    <span className="font-medium">{t("aiAnalysis.impact")}: </span>
                    {risk.impact}
                  </div>
                ) : null}
                {risk.cause ? (
                  <div className="text-muted-foreground">
                    <span className="font-medium">{t("aiAnalysis.cause")}: </span>
                    {risk.cause}
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        ) : (
          <div className="text-xs text-muted-foreground">
            {t("aiAnalysis.noCriticalRisks")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ExecutiveCard({
  a,
  className = "",
}: {
  a: ProjectAIAnalysis;
  className?: string;
}) {
  const { t } = useT();
  const e = a.executive;
  const tone = executiveTone(e.project_status);
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-violet-500">🧠</span>
          <Brain className="h-4 w-4" />
          {t("aiAnalysis.cardExecutive")}
        </CardTitle>
        <Badge variant="outline" className={toneClass(tone)}>
          {e.project_status}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="leading-relaxed">{e.summary}</p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <ExecRow label={t("aiAnalysis.biggestProblem")} value={e.biggest_problem} />
          <ExecRow label={t("aiAnalysis.financialLbl")} value={e.financial_status} />
          <ExecRow label={t("aiAnalysis.scheduleLbl")} value={e.schedule_status} />
          <ExecRow label={t("aiAnalysis.urgentAction")} value={e.urgent_action} accent />
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Small reusable bits
// ---------------------------------------------------------------------------

function Row({
  label,
  value,
  strong,
  tone,
}: {
  label: string;
  value: string;
  strong?: boolean;
  tone?: StatusTone;
}) {
  const valueClass = tone
    ? tone === "critical"
      ? "text-rose-600 dark:text-rose-400"
      : tone === "good"
        ? "text-emerald-600 dark:text-emerald-400"
        : ""
    : "";
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={
          (strong ? "font-semibold " : "font-medium ") + valueClass
        }
      >
        {value}
      </span>
    </div>
  );
}

function ExecRow({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  if (!value) return null;
  return (
    <div
      className={
        "rounded-md border p-2 " +
        (accent
          ? "border-violet-200 bg-violet-50 dark:border-violet-900 dark:bg-violet-950/40"
          : "bg-card")
      }
    >
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="text-sm">{value}</div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i} className={i === 5 ? "md:col-span-2 xl:col-span-3" : ""}>
          <CardHeader>
            <Skeleton className="h-5 w-1/2" />
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </CardContent>
        </Card>
      ))}
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
          <div className="font-medium">{t("aiAnalysis.loadFailed")}</div>
          <div className="text-sm text-muted-foreground">{message}</div>
        </div>
        <Button onClick={onRetry} variant="outline" size="sm">
          {t("aiAnalysis.tryAgain")}
        </Button>
      </CardContent>
    </Card>
  );
}
