"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  RefreshCw,
  Bot,
  CheckSquare,
  AlertTriangle,
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
import type { DailyBriefing } from "@/types/dashboard";

/**
 * Top-of-dashboard card that pulls a 1-paragraph executive briefing of the
 * last 24 hours from the backend. Uses Claude when an API key is set,
 * otherwise rule-based copy.
 */
export function DailyBriefingCard() {
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load(force = false) {
    if (force) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await api.dashboard.dailyBriefing(force);
      setBriefing(data);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Failed to load briefing";
      if (force) toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load(false);
  }, []);

  if (loading) {
    return (
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-cyan-500/5">
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!briefing) return null;

  const sourceLabel =
    briefing.source === "llm" ? "AI Generated" : "Rule-based";

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-cyan-500/5">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Günlük Brifing
            </CardTitle>
            <p className="text-sm font-semibold text-foreground/90 mt-1">
              {briefing.headline}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge
              variant="outline"
              className="text-[10px] gap-1 bg-primary/10 border-primary/30"
            >
              <Bot className="h-3 w-3" />
              {sourceLabel}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              onClick={() => load(true)}
              disabled={refreshing}
            >
              <RefreshCw
                className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`}
              />
              Yenile
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-foreground/85 leading-relaxed">
          {briefing.summary}
        </p>

        {/* Two-column: highlights + decisions */}
        <div className="grid gap-4 md:grid-cols-2">
          {briefing.highlights.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                Öne Çıkanlar
              </p>
              <ul className="space-y-1.5">
                {briefing.highlights.map((h, i) => (
                  <li key={i} className="text-xs flex items-start gap-2">
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                    <span className="leading-relaxed">{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {briefing.decisions.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                <CheckSquare className="h-3 w-3" />
                Bugün Yapılacaklar
              </p>
              <ul className="space-y-1.5">
                {briefing.decisions.map((d, i) => (
                  <li key={i} className="text-xs flex items-start gap-2">
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                    <span className="leading-relaxed">{d}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <p className="text-[10px] text-muted-foreground text-right">
          {new Date(briefing.generated_at).toLocaleString()}
        </p>
      </CardContent>
    </Card>
  );
}
