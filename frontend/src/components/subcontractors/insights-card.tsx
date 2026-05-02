"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Bot, RefreshCw, AlertCircle, TrendingUp, ShieldAlert, Wallet, Calendar,
  Sparkles, ArrowRight, Filter,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import type { AIInsight, SubcontractorInsights } from "@/types/subcontractor";

const SEVERITY_RANK: Record<string, number> = { critical: 0, warning: 1, info: 2 };
const CATEGORIES = ["all", "financial", "schedule", "risk", "performance"] as const;
type CategoryFilter = (typeof CATEGORIES)[number];

const CAT_LABEL: Record<CategoryFilter, string> = {
  all: "All",
  financial: "Financial",
  schedule: "Schedule",
  risk: "Risk",
  performance: "Performance",
};

const CAT_ICON: Record<string, React.ReactNode> = {
  financial: <Wallet className="h-3 w-3" />,
  schedule: <Calendar className="h-3 w-3" />,
  risk: <ShieldAlert className="h-3 w-3" />,
  performance: <TrendingUp className="h-3 w-3" />,
};

interface Props {
  subcontractorId: number;
  insights: SubcontractorInsights | null;
  onRefreshed: (data: SubcontractorInsights) => void;
}

export function SubcontractorInsightsCard({ subcontractorId, insights, onRefreshed }: Props) {
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<CategoryFilter>("all");

  const sorted = useMemo(() => {
    if (!insights) return [];
    const list = [...insights.insights];
    if (filter !== "all") {
      return list.filter((i) => i.category === filter)
        .sort((a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9));
    }
    return list.sort((a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9));
  }, [insights, filter]);

  const counts = useMemo(() => {
    const base: Record<string, number> = { all: 0, financial: 0, schedule: 0, risk: 0, performance: 0 };
    if (!insights) return base;
    for (const i of insights.insights) {
      base.all++;
      if (i.category && base[i.category] !== undefined) base[i.category]++;
    }
    return base;
  }, [insights]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const fresh = await api.subcontractors.aiInsights(subcontractorId, true);
      onRefreshed(fresh);
      toast.success("Insights refreshed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Refresh failed");
    } finally { setRefreshing(false); }
  }

  const hasMockInsights = useMemo(
    () => insights?.insights.some((i) => i.source === "llm_mock") ?? false,
    [insights]
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <CardTitle className="text-base flex items-center gap-2">
            <Bot className="h-4 w-4" /> AI Insights
            {insights && (
              <span className={`text-xs px-2 py-0.5 rounded-full ml-1 ${
                insights.overall_health === "good" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                : insights.overall_health === "critical" ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
              }`}>
                {insights.overall_health}
              </span>
            )}
          </CardTitle>
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw className={`h-3 w-3 mr-1 ${refreshing ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>

        {/* Category filter */}
        {insights && insights.insights.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap pt-2">
            <Filter className="h-3 w-3 text-muted-foreground" />
            {CATEGORIES.map((c) => {
              const count = counts[c];
              if (c !== "all" && count === 0) return null;
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => setFilter(c)}
                  className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors flex items-center gap-1 ${
                    filter === c
                      ? "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 border-indigo-300 dark:border-indigo-700"
                      : "bg-muted/30 hover:bg-muted/60 border-border text-muted-foreground"
                  }`}
                >
                  {c !== "all" && CAT_ICON[c]} {CAT_LABEL[c]} ({count})
                </button>
              );
            })}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {!insights || insights.insights.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Bot className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>No insights yet. They are generated as contracts and payments are added.</p>
          </div>
        ) : sorted.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">
            No insights in this category.
          </div>
        ) : (
          <div className="space-y-2">
            {sorted.map((ins, i) => (
              <InsightRow key={i} insight={ins} />
            ))}
          </div>
        )}

        {hasMockInsights && (
          <div className="mt-4 flex items-start gap-2 p-2.5 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 text-xs text-amber-700 dark:text-amber-300">
            <Sparkles className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
            <span>
              Some insights are LLM mock-generated. Once ANTHROPIC_API_KEY is added to
              the .env file, click &quot;Refresh&quot; to get real LLM analysis.
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function InsightRow({ insight }: { insight: AIInsight }) {
  const sevColor =
    insight.severity === "critical" ? "border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-950/20"
    : insight.severity === "warning" ? "border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20"
    : "border-border bg-muted/30";

  const iconColor =
    insight.severity === "critical" ? "text-red-500"
    : insight.severity === "warning" ? "text-amber-500"
    : "text-blue-500";

  const icon = insight.type === "prediction" ? <TrendingUp className="h-4 w-4" />
    : insight.type === "alert" ? <AlertCircle className="h-4 w-4" />
    : <Bot className="h-4 w-4" />;

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${sevColor}`}>
      <div className={`mt-0.5 ${iconColor} flex-shrink-0`}>{icon}</div>
      <div className="flex-1 min-w-0 space-y-1">
        {insight.title && (
          <div className="text-sm font-semibold flex items-center gap-2">
            {insight.title}
            {insight.source === "llm_mock" && (
              <span className="text-[9px] px-1.5 py-0 rounded bg-muted/80 text-muted-foreground border">mock</span>
            )}
            {insight.source === "llm" && (
              <span className="text-[9px] px-1.5 py-0 rounded bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-700">LLM</span>
            )}
          </div>
        )}
        <div className="text-sm">{insight.body || insight.message}</div>
        {insight.action && (
          <div className="flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 pt-1">
            <ArrowRight className="h-3 w-3" />
            <span className="font-medium">Suggested action:</span> {insight.action}
          </div>
        )}
        {insight.category && (
          <div className="text-[10px] text-muted-foreground pt-0.5">
            {CAT_ICON[insight.category]
              ? <span className="inline-flex items-center gap-1">{CAT_ICON[insight.category]} {CAT_LABEL[insight.category as CategoryFilter] ?? insight.category}</span>
              : insight.category}
          </div>
        )}
      </div>
    </div>
  );
}
