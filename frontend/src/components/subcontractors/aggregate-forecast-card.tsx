"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ComposedChart, Bar, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from "recharts";
import { TrendingUp, AlertTriangle, Sparkles, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import { formatRubAxisTick, formatRubCompact } from "@/lib/formatters";
import { useT } from "@/lib/i18n/provider";
import type { AggregateCashFlowForecast } from "@/types/subcontractor";

interface ChartRow {
  month: string;
  history?: number;
  best?: number;
  likely?: number;
  worst?: number;
  band?: [number, number];
}

export function AggregateForecastCard() {
  const { t } = useT();
  const [data, setData] = useState<AggregateCashFlowForecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const fc = await api.subcontractors.aggregateForecast();
        if (!cancelled) setData(fc);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const chartData = useMemo<ChartRow[]>(() => {
    if (!data) return [];
    const rows: ChartRow[] = [];
    for (const h of data.historical) {
      rows.push({ month: h.month, history: parseFloat(h.paid_amount) || 0 });
    }
    for (const f of data.forecast) {
      const w = parseFloat(f.worst_case) || 0;
      const l = parseFloat(f.likely) || 0;
      const b = parseFloat(f.best_case) || 0;
      rows.push({ month: f.month, worst: w, likely: l, best: b, band: [w, b] });
    }
    return rows;
  }, [data]);

  const todayMonth = useMemo(() => {
    if (!data || data.historical.length === 0) return null;
    return data.historical[data.historical.length - 1]?.month ?? null;
  }, [data]);

  const total3mLikely = useMemo(() => {
    if (!data) return 0;
    return data.forecast.reduce((acc, f) => acc + (parseFloat(f.likely) || 0), 0);
  }, [data]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" /> {t("subs.aggregateForecast")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[260px] animate-pulse bg-muted/30 rounded" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" /> {t("subs.aggregateForecast")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">
            {error ?? "No data available"}
          </div>
        </CardContent>
      </Card>
    );
  }

  const confidencePct = Math.round(data.confidence * 100);
  const confidenceColor =
    data.confidence >= 0.7 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800"
    : data.confidence >= 0.5 ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 border-amber-200 dark:border-amber-800"
    : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800";

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-2 flex-wrap">
        <div className="space-y-0.5">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" /> {t("subs.aggregateForecast")}
            <span className={`text-xs px-2 py-0.5 rounded-full border ${confidenceColor}`}>
              {t("forecast.confidence")}: {confidencePct}%
            </span>
          </CardTitle>
          <div className="text-xs text-muted-foreground flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <Users className="h-3 w-3" />
              {t("forecast.activeOf", {
                active: data.active_subcontractors,
                total: data.total_subcontractors,
              })}
            </span>
            <span className="font-semibold text-foreground/80">
              {t("forecast.likelyTotal")}: {formatRubCompact(total3mLikely)}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {data.insufficient_data_count > 0 && (
          <div className="flex items-start gap-2 p-2 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 text-[11px] text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
            <span>
              {data.insufficient_data_count}/{data.active_subcontractors} subcontractors have
              {" "}<strong>&lt; 12 months</strong> of history — forecasts for these firms
              {" "}have lower confidence. Seasonality factor is averaged.
            </span>
          </div>
        )}

        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={chartData} margin={{ top: 6, right: 6, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="month" className="text-xs" tick={{ fontSize: 10 }} />
            <YAxis tickFormatter={(v) => formatRubAxisTick(v)} className="text-xs" tick={{ fontSize: 10 }} width={48} />
            <Tooltip
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={((value: unknown, name: string) => {
                if (Array.isArray(value)) {
                  const [lo, hi] = value as [number, number];
                  return [`${formatRubCompact(lo)} – ${formatRubCompact(hi)}`, t("forecast.uncertainty")];
                }
                if (typeof value !== "number") return [String(value), name];
                const labelMap: Record<string, string> = {
                  history: t("forecast.actual"),
                  best: t("forecast.best"),
                  likely: t("forecast.likely"),
                  worst: t("forecast.worst"),
                };
                return [formatRubCompact(value), labelMap[name] ?? name];
              }) as any}
              contentStyle={{ borderRadius: 8, fontSize: 11 }}
            />
            <Legend
              verticalAlign="top"
              wrapperStyle={{ fontSize: 10, paddingBottom: 4 }}
              iconType="line"
              formatter={(v: string) => {
                const map: Record<string, string> = {
                  history: t("forecast.actual"),
                  best: t("forecast.best"),
                  likely: t("forecast.likely"),
                  worst: t("forecast.worst"),
                };
                return map[v] ?? v;
              }}
            />
            {todayMonth && (
              <ReferenceLine
                x={todayMonth}
                stroke="#6366f1"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{ value: t("forecast.today"), position: "top", fill: "#6366f1", fontSize: 10 }}
              />
            )}
            <Bar dataKey="history" name="history" fill="#10b981" radius={[3, 3, 0, 0]} barSize={18} />
            <Area dataKey="band" name="band" fill="#6366f1" fillOpacity={0.12} stroke="none" legendType="none" />
            <Line type="monotone" dataKey="best" name="best" stroke="#10b981" strokeWidth={1.5} strokeDasharray="4 3" dot={{ r: 2 }} connectNulls />
            <Line type="monotone" dataKey="likely" name="likely" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
            <Line type="monotone" dataKey="worst" name="worst" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4 3" dot={{ r: 2 }} connectNulls />
          </ComposedChart>
        </ResponsiveContainer>

        {data.insights.length > 0 && (
          <div className="space-y-1 pt-1 border-t">
            {data.insights.slice(0, 3).map((ins, i) => (
              <div key={i} className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
                <Sparkles className="h-2.5 w-2.5 mt-0.5 text-indigo-500 flex-shrink-0" />
                <span>{ins}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
