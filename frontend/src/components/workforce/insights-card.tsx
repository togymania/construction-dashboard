"use client";

import { Sparkles, TrendingUp, TrendingDown, AlertTriangle, BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkforceInsightsBundle, WorkforceInsight } from "@/types/workforce";

const TONE_STYLES: Record<
  string,
  { border: string; bg: string; text: string; icon: typeof TrendingUp }
> = {
  positive: {
    border: "border-emerald-500/20",
    bg: "bg-emerald-500/5",
    text: "text-emerald-500",
    icon: TrendingUp,
  },
  negative: {
    border: "border-amber-500/20",
    bg: "bg-amber-500/5",
    text: "text-amber-500",
    icon: TrendingDown,
  },
  warning: {
    border: "border-orange-500/20",
    bg: "bg-orange-500/5",
    text: "text-orange-500",
    icon: AlertTriangle,
  },
  neutral: {
    border: "border-foreground/8",
    bg: "bg-muted/30",
    text: "text-muted-foreground",
    icon: BarChart3,
  },
};

interface InsightsCardProps {
  insights: WorkforceInsightsBundle | null;
}

export function WorkforceInsightsCard({ insights }: InsightsCardProps) {
  if (!insights) return null;

  const allEmpty =
    insights.daily.length === 0 &&
    insights.weekly.length === 0 &&
    insights.monthly.length === 0;

  if (allEmpty) return null;

  return (
    <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm sticky top-24">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <div className="h-6 w-6 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
          </div>
          AI Insights
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {insights.daily.length > 0 && (
          <InsightSection title="Today" insights={insights.daily} />
        )}
        {insights.weekly.length > 0 && (
          <InsightSection title="This Week" insights={insights.weekly} />
        )}
        {insights.monthly.length > 0 && (
          <InsightSection title="30-Day Overview" insights={insights.monthly} />
        )}
      </CardContent>
    </Card>
  );
}

function InsightSection({
  title,
  insights,
}: {
  title: string;
  insights: WorkforceInsight[];
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-2">
        {title}
      </div>
      <div className="space-y-2">
        {insights.map((insight, i) => {
          const style = TONE_STYLES[insight.tone] || TONE_STYLES.neutral;
          return (
            <div
              key={i}
              className={
                "flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm transition-colors " +
                style.border +
                " " +
                style.bg
              }
            >
              <span className="text-base leading-none mt-0.5 shrink-0">{insight.icon}</span>
              <span className="text-foreground/90 leading-snug">{insight.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
