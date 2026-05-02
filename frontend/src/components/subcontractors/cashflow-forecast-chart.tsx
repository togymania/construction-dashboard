"use client";

import { useMemo } from "react";
import {
  ComposedChart, Bar, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine, ReferenceDot,
} from "recharts";
import {
  AlertTriangle, Sparkles, TrendingUp, Info, Calendar,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatRubAxisTick, formatRubCompact } from "@/lib/formatters";
import type { CashFlowForecast } from "@/types/subcontractor";

interface Props {
  forecast: CashFlowForecast | null;
  loading?: boolean;
}

interface ChartRow {
  month: string;
  isHistory: boolean;
  history?: number;
  best?: number;
  likely?: number;
  worst?: number;
  band?: [number, number]; // [worst, best] for area shading
}

export function CashFlowForecastChart({ forecast, loading }: Props) {
  const chartData = useMemo<ChartRow[]>(() => {
    if (!forecast) return [];
    const rows: ChartRow[] = [];

    // History bars
    for (const h of forecast.historical) {
      rows.push({
        month: h.month,
        isHistory: true,
        history: parseFloat(h.paid_amount) || 0,
      });
    }

    // Forecast lines + confidence band
    for (const f of forecast.forecast) {
      const w = parseFloat(f.worst_case) || 0;
      const l = parseFloat(f.likely) || 0;
      const b = parseFloat(f.best_case) || 0;
      rows.push({
        month: f.month,
        isHistory: false,
        worst: w,
        likely: l,
        best: b,
        band: [w, b],
      });
    }
    return rows;
  }, [forecast]);

  // Index of last historical row (for vertical "today" line)
  const todayMonthIdx = useMemo(() => {
    if (!forecast || forecast.historical.length === 0) return -1;
    return forecast.historical.length - 1;
  }, [forecast]);

  // Contract end markers — find their position in chart
  const contractEndMarkers = useMemo(() => {
    if (!forecast) return [];
    const allMonths = chartData.map((r) => r.month);
    return forecast.contract_end_dates
      .map((c) => {
        const monthKey = c.end_date.substring(0, 7);
        if (allMonths.includes(monthKey)) {
          return { month: monthKey, label: c.contract_label };
        }
        return null;
      })
      .filter((x): x is { month: string; label: string } => x !== null);
  }, [forecast, chartData]);

  if (loading) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Cash Flow Forecast</CardTitle></CardHeader>
        <CardContent><div className="h-[340px] animate-pulse bg-muted/30 rounded" /></CardContent>
      </Card>
    );
  }

  if (!forecast || (forecast.historical.length === 0 && forecast.forecast.length === 0)) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Cash Flow Forecast</CardTitle></CardHeader>
        <CardContent>
          <div className="h-[300px] flex flex-col items-center justify-center text-sm text-muted-foreground gap-2">
            <Sparkles className="h-8 w-8 opacity-30" />
            <p>Not enough payment history to generate a forecast.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const confidencePct = Math.round(forecast.confidence * 100);
  const confidenceColor =
    forecast.confidence >= 0.7 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800"
    : forecast.confidence >= 0.5 ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 border-amber-200 dark:border-amber-800"
    : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800";

  const methodLabel = forecast.method === "ema_seasonal" ? "EMA + Seasonality"
    : forecast.method === "naive_average" ? "Naive Average (insufficient data)"
    : "—";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 flex-wrap">
        <CardTitle className="text-base flex items-center gap-2">
          <TrendingUp className="h-4 w-4" /> Cash Flow Forecast
          <span className={`text-xs px-2 py-0.5 rounded-full border ${confidenceColor}`}>
            Confidence: {confidencePct}%
          </span>
        </CardTitle>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Info className="h-3 w-3" />
          <span>{methodLabel} · {forecast.months_of_data} months of data</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {forecast.insufficient_data && (
          <div className="flex items-start gap-2 p-2.5 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 text-xs text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <div>
              <strong>Forecast based on &lt; 12 months of history.</strong> Seasonality
              is disabled — only the recent average is used. Confidence will improve
              as more data accumulates.
            </div>
          </div>
        )}

        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="month" className="text-xs" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v) => formatRubAxisTick(v)} className="text-xs" tick={{ fontSize: 11 }} width={56} />
            <Tooltip
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={((value: unknown, name: string) => {
                if (Array.isArray(value)) {
                  const [lo, hi] = value as [number, number];
                  return [`${formatRubCompact(lo)} – ${formatRubCompact(hi)}`, "Confidence band"];
                }
                if (typeof value !== "number") return [String(value), name];
                const labelMap: Record<string, string> = {
                  history: "Actual",
                  best: "Best",
                  likely: "Likely",
                  worst: "Worst",
                };
                return [formatRubCompact(value), labelMap[name] ?? name];
              }) as any}
              contentStyle={{ borderRadius: 8, fontSize: 12 }}
            />
            <Legend
              verticalAlign="top"
              wrapperStyle={{ fontSize: 11, paddingBottom: 8 }}
              iconType="line"
              formatter={(v: string) => {
                const map: Record<string, string> = {
                  history: "Actual",
                  best: "Best case",
                  likely: "Likely case",
                  worst: "Worst case",
                  band: "Confidence band",
                };
                return map[v] ?? v;
              }}
            />

            {/* Today divider */}
            {todayMonthIdx >= 0 && chartData[todayMonthIdx] && (
              <ReferenceLine
                x={chartData[todayMonthIdx].month}
                stroke="#6366f1"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{ value: "Today", position: "top", fill: "#6366f1", fontSize: 11 }}
              />
            )}

            {/* Contract end markers */}
            {contractEndMarkers.map((m, idx) => (
              <ReferenceDot
                key={idx}
                x={m.month}
                y={0}
                r={5}
                fill="#ef4444"
                stroke="#fff"
                strokeWidth={2}
                label={{ value: "Contract end", position: "bottom", fill: "#ef4444", fontSize: 10 }}
              />
            ))}

            {/* Historical bars */}
            <Bar
              dataKey="history"
              name="history"
              fill="#10b981"
              radius={[4, 4, 0, 0]}
              barSize={28}
            />

            {/* Confidence band */}
            <Area
              dataKey="band"
              name="band"
              fill="#6366f1"
              fillOpacity={0.12}
              stroke="none"
            />

            {/* Forecast scenario lines */}
            <Line
              type="monotone"
              dataKey="best"
              name="best"
              stroke="#10b981"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={{ r: 3, fill: "#10b981" }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="likely"
              name="likely"
              stroke="#6366f1"
              strokeWidth={2.5}
              dot={{ r: 4, fill: "#6366f1" }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="worst"
              name="worst"
              stroke="#f59e0b"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={{ r: 3, fill: "#f59e0b" }}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>

        {/* Insights bullets */}
        {forecast.insights.length > 0 && (
          <div className="space-y-1.5 pt-1">
            {forecast.insights.map((insight, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                <Sparkles className="h-3 w-3 mt-0.5 text-indigo-500 flex-shrink-0" />
                <span>{insight}</span>
              </div>
            ))}
          </div>
        )}

        {/* Contract end dates list */}
        {forecast.contract_end_dates.length > 0 && (
          <div className="pt-2 border-t">
            <div className="text-xs font-semibold text-muted-foreground mb-1.5 flex items-center gap-1">
              <Calendar className="h-3 w-3" /> Upcoming contract endings
            </div>
            <div className="space-y-1">
              {forecast.contract_end_dates.map((c) => (
                <div key={c.contract_id} className="flex items-center justify-between text-xs">
                  <span className="truncate">{c.contract_label}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {c.end_date} · remaining {formatRubCompact(parseFloat(c.remaining_amount))}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
