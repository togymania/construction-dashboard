"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  RefreshCw,
  Sparkles,
  Trophy,
  Scale,
  AlertTriangle,
  Brain,
  BarChart3,
  Receipt,
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
import type {
  BidSpreadLevel,
  TenderAIAnalysis,
} from "@/types/tender";

function spreadTone(level: BidSpreadLevel): string {
  switch (level) {
    case "ABNORMAL":
      return "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300";
    case "WIDE":
      return "border-amber-200 bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300";
    default:
      return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300";
  }
}

function confidenceTone(pct: number): string {
  if (pct >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (pct >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-rose-600 dark:text-rose-400";
}

export default function TenderAIAnalysisPage() {
  const params = useParams<{ id: string; tid: string }>();
  const projectId = parseInt(params.id, 10);
  const tenderId = parseInt(params.tid, 10);
  const router = useRouter();
  const { locale } = useT();

  const [a, setA] = useState<TenderAIAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(force = false) {
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await api.tenders.aiAnalysis(tenderId, force);
      setA(data);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Failed to load analysis";
      setError(msg);
      if (force) toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (tenderId > 0) load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenderId, locale]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              router.push(`/projects/${projectId}/tenders/${tenderId}`)
            }
          >
            <ArrowLeft className="mr-1 h-4 w-4" /> Back
          </Button>
          <div className="rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 p-2 text-white shadow-sm">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold">AI Tender Analysis</h1>
            <p className="text-sm text-muted-foreground">
              Bid comparison, risks and recommendation
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {a?.source ? (
            <Badge variant={a.source === "llm" ? "default" : "secondary"}>
              {a.source === "llm" ? "AI" : "Rule-based"}
            </Badge>
          ) : null}
          {a?.generated_at ? (
            <span className="text-xs text-muted-foreground">
              {new Date(a.generated_at).toLocaleString()}
            </span>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={() => load(true)}
            disabled={refreshing}
          >
            <RefreshCw
              className={"mr-1 h-4 w-4 " + (refreshing ? "animate-spin" : "")}
            />
            Refresh
          </Button>
        </div>
      </div>

      {loading && !a ? (
        <LoadingGrid />
      ) : error ? (
        <Card>
          <CardContent className="p-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : a ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <OverviewCard a={a} />
          <ComparisonCard a={a} />
          <AnalysisCard a={a} />
          <RisksCard a={a} />
          <RecommendationCard a={a} />
          <ExecutiveCard a={a} className="md:col-span-2 xl:col-span-3" />
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cards
// ---------------------------------------------------------------------------

function OverviewCard({ a }: { a: TenderAIAnalysis }) {
  const o = a.overview;
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-blue-500">📊</span>
          <BarChart3 className="h-4 w-4" />
          Overview
        </CardTitle>
        <Badge variant="outline" className={spreadTone(o.bid_spread_level)}>
          Spread {o.bid_spread_pct.toFixed(0)}% · {o.bid_spread_level}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Row label="Bid count" value={String(o.bid_count)} />
        <Row label="Average total" value={fmt(o.average_total)} />
        {o.lowest ? (
          <Row
            label="Lowest"
            value={`${o.lowest.company} · ${fmt(o.lowest.total_amount)}`}
            tone="good"
          />
        ) : null}
        {o.highest ? (
          <Row
            label="Highest"
            value={`${o.highest.company} · ${fmt(o.highest.total_amount)}`}
            tone="critical"
          />
        ) : null}
      </CardContent>
    </Card>
  );
}

function ComparisonCard({ a }: { a: TenderAIAnalysis }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-emerald-500">💰</span>
          <Receipt className="h-4 w-4" />
          Comparison
        </CardTitle>
      </CardHeader>
      <CardContent>
        {a.comparison.length === 0 ? (
          <p className="text-sm text-muted-foreground">No bids yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {a.comparison.map((c, i) => (
              <li
                key={i}
                className="flex items-center justify-between rounded border bg-card px-2 py-1"
              >
                <span className="truncate font-medium">{c.company}</span>
                <span className="flex items-center gap-2 text-xs">
                  <span className="font-semibold">{fmt(c.total_amount)}</span>
                  {c.delivery_days != null ? (
                    <Badge variant="secondary" className="text-[10px]">
                      {c.delivery_days}d
                    </Badge>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function AnalysisCard({ a }: { a: TenderAIAnalysis }) {
  const an = a.analysis;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-violet-500">⚖️</span>
          <Scale className="h-4 w-4" />
          Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Row label="Best price" value={an.best_price_company ?? "—"} />
        <Row label="Fastest" value={an.fastest_company ?? "—"} />
        <Row label="Most balanced" value={an.most_balanced_company ?? "—"} />
        {an.comments ? (
          <p className="mt-2 rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">
            {an.comments}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function RisksCard({ a }: { a: TenderAIAnalysis }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-rose-500">⚠️</span>
          <AlertTriangle className="h-4 w-4" />
          Risks
        </CardTitle>
      </CardHeader>
      <CardContent>
        {a.risks.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No risks flagged.
          </p>
        ) : (
          <ul className="space-y-2">
            {a.risks.map((r, i) => (
              <li key={i} className="rounded border bg-card p-2 text-xs">
                <div className="font-medium">
                  {r.company} · {r.risk}
                </div>
                {r.cause ? (
                  <div className="text-muted-foreground">{r.cause}</div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function RecommendationCard({ a }: { a: TenderAIAnalysis }) {
  const r = a.recommendation;
  return (
    <Card className="border-amber-300 bg-amber-50/40 dark:border-amber-900 dark:bg-amber-950/20">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-amber-500">🏆</span>
          <Trophy className="h-4 w-4" />
          Recommendation
        </CardTitle>
        <span className={"text-xs font-semibold " + confidenceTone(r.confidence_pct)}>
          {r.confidence_pct.toFixed(0)}% confidence
        </span>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div>
          <span className="text-xs uppercase text-muted-foreground">
            Chosen
          </span>
          <div className="text-lg font-semibold">
            {r.chosen_company ?? "—"}
          </div>
        </div>
        {r.reason ? <p className="text-sm">{r.reason}</p> : null}
        {r.alternative_company ? (
          <div className="rounded-md bg-card p-2 text-xs">
            <span className="font-medium text-muted-foreground">
              Alternative:{" "}
            </span>
            {r.alternative_company}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ExecutiveCard({
  a,
  className = "",
}: {
  a: TenderAIAnalysis;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="text-fuchsia-500">🧠</span>
          <Brain className="h-4 w-4" />
          Executive Summary
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed">
          {a.executive_summary || "No summary."}
        </p>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "critical";
}) {
  const valueClass = tone
    ? tone === "critical"
      ? "text-rose-600 dark:text-rose-400"
      : "text-emerald-600 dark:text-emerald-400"
    : "";
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={"font-medium " + valueClass}>{value}</span>
    </div>
  );
}

function fmt(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  return formatRubCompact(n);
}

function LoadingGrid() {
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
