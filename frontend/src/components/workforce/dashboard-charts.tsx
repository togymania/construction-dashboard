"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  WorkforceKPIBundle,
  WorkforceKPIDailyPoint,
  WorkforceKPITopPosition,
  WorkforceKPIWeeklyBucket,
  WorkforceDisciplinePoint,
  WorkforceDisciplineTodaySummary,
  WorkforceCategory,
} from "@/types/workforce";

// Premium color palette
const COLOR_DIRECT = "oklch(0.62 0.20 270)"; // indigo
const COLOR_INDIRECT = "oklch(0.70 0.15 200)"; // cyan
const COLOR_SUBCONTRACTOR = "oklch(0.68 0.18 155)"; // emerald
const COLOR_TOTAL = "oklch(0.75 0.18 65)"; // amber/gold

// Discipline colors
const COLOR_ELECTRICAL = "oklch(0.65 0.20 270)"; // indigo-purple
const COLOR_MECHANICAL = "oklch(0.68 0.22 25)"; // warm red-orange
const COLOR_CIVIL = "oklch(0.72 0.18 145)"; // teal-green

const CATEGORY_COLOR: Record<WorkforceCategory, string> = {
  direct: COLOR_DIRECT,
  indirect: COLOR_INDIRECT,
  subcontractor: COLOR_SUBCONTRACTOR,
};

const CATEGORY_LABEL: Record<WorkforceCategory, string> = {
  direct: "Direct",
  indirect: "Indirect",
  subcontractor: "Subcontractor",
};

// Shared tooltip style
const tooltipStyle = {
  fontSize: 12,
  borderRadius: 12,
  border: "1px solid oklch(1 0 0 / 10%)",
  boxShadow: "0 8px 32px oklch(0 0 0 / 20%)",
  backdropFilter: "blur(16px)",
};

interface Props {
  kpis: WorkforceKPIBundle;
}

export function WorkforceDashboardCharts({ kpis }: Props) {
  return (
    <div className="space-y-6">
      {/* Row 1: Daily Trend (full width - hero chart) */}
      <DailyTrendChart trend={kpis.daily_trend} />

      {/* Row 2: Weekly Comparison + Discipline Donut */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <WeeklyComparisonChart buckets={kpis.weekly_buckets} />
        <DisciplineDonutChart
          today={kpis.discipline_today}
          trend={kpis.discipline_trend}
        />
      </div>

      {/* Row 3: Top Positions + Category Bar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TopPositionsChart positions={kpis.top_positions} />
        <TodayByCategoryChart bundle={kpis} />
      </div>
    </div>
  );
}

// =============================================================================
// Daily Trend (REDESIGNED) - smooth line + stacked areas with total line
// =============================================================================
function DailyTrendChart({ trend }: { trend: WorkforceKPIDailyPoint[] }) {
  if (trend.length === 0) {
    return (
      <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-base font-medium">Daily Workforce Trend</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-16 text-sm text-muted-foreground">
          Upload data to see daily trends
        </CardContent>
      </Card>
    );
  }

  const data = trend.map((p) => ({
    date: p.snapshot_date.slice(5), // MM-DD
    fullDate: p.snapshot_date,
    direct: p.direct_present,
    subcontractor: p.subcontractor_present,
    total: p.total_present,
  }));

  return (
    <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">
            Daily Workforce Trend
          </CardTitle>
          <span className="text-xs text-muted-foreground tabular-nums">
            Last {trend.length} {trend.length === 1 ? "day" : "days"}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={data} margin={{ top: 10, right: 16, bottom: 5, left: 0 }}>
            <defs>
              <linearGradient id="grad-direct-v2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLOR_DIRECT} stopOpacity={0.5} />
                <stop offset="100%" stopColor={COLOR_DIRECT} stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="grad-sub-v2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLOR_SUBCONTRACTOR} stopOpacity={0.5} />
                <stop offset="100%" stopColor={COLOR_SUBCONTRACTOR} stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/30" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={40}
            />
            <Tooltip
              labelFormatter={(_label, payload) => {
                const p = payload?.[0]?.payload;
                return p?.fullDate ?? _label;
              }}
              contentStyle={tooltipStyle}
              formatter={(value, name) => {
                const labels: Record<string, string> = {
                  direct: "Direct",
                  subcontractor: "Subcontractor",
                  total: "Total Workforce",
                };
                return [String(value), labels[String(name)] || String(name)];
              }}
            />
            <Legend
              verticalAlign="top"
              height={28}
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: 12 }}
            />
            <Area
              type="monotone"
              dataKey="direct"
              stroke={COLOR_DIRECT}
              strokeWidth={2}
              fill="url(#grad-direct-v2)"
              name="Direct"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2 }}
            />
            <Area
              type="monotone"
              dataKey="subcontractor"
              stroke={COLOR_SUBCONTRACTOR}
              strokeWidth={2}
              fill="url(#grad-sub-v2)"
              name="Subcontractor"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2 }}
            />
            <Line
              type="monotone"
              dataKey="total"
              stroke={COLOR_TOTAL}
              strokeWidth={2.5}
              strokeDasharray="6 3"
              name="Total"
              dot={false}
              activeDot={{ r: 5, strokeWidth: 2, fill: COLOR_TOTAL }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Weekly Comparison (REDESIGNED) - This week vs Last week with delta badge
// =============================================================================
function WeeklyComparisonChart({ buckets }: { buckets: WorkforceKPIWeeklyBucket[] }) {
  if (buckets.length === 0) {
    return (
      <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-base font-medium">Weekly Comparison</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-16 text-sm text-muted-foreground">
          Need at least 1 week of data
        </CardContent>
      </Card>
    );
  }

  // Show the last 2 weeks with a delta badge
  const lastTwo = buckets.slice(-2);
  const thisWeek = lastTwo[lastTwo.length - 1];
  const lastWeek = lastTwo.length >= 2 ? lastTwo[0] : null;
  const diff = lastWeek
    ? Math.round(thisWeek.avg_total_present - lastWeek.avg_total_present)
    : null;

  const barData = lastTwo.map((b, i) => ({
    label: i === lastTwo.length - 1 ? "This Week" : "Last Week",
    fullWeek: b.week_start,
    direct: Math.round(b.avg_direct),
    indirect: Math.round(b.avg_indirect),
    subcontractor: Math.round(b.avg_subcontractor),
    total: Math.round(b.avg_total_present),
    days: b.days_recorded,
  }));

  return (
    <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">Weekly Average</CardTitle>
          {diff !== null && (
            <span
              className={
                "inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full tabular-nums " +
                (diff > 0
                  ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                  : diff < 0
                  ? "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                  : "bg-muted text-muted-foreground border border-foreground/10")
              }
            >
              {diff > 0 ? "+" : ""}
              {diff}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={barData} margin={{ top: 10, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/30" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
            <Tooltip
              labelFormatter={(_label, payload) => {
                const p = payload?.[0]?.payload;
                return p ? `Week of ${p.fullWeek} (${p.days} days)` : _label;
              }}
              contentStyle={tooltipStyle}
            />
            <Legend
              verticalAlign="top"
              height={28}
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: 12 }}
            />
            <Bar
              dataKey="direct"
              stackId="a"
              fill={COLOR_DIRECT}
              name="Direct"
              radius={[0, 0, 0, 0]}
            />
            <Bar
              dataKey="indirect"
              stackId="a"
              fill={COLOR_INDIRECT}
              name="Indirect"
            />
            <Bar
              dataKey="subcontractor"
              stackId="a"
              fill={COLOR_SUBCONTRACTOR}
              name="Subcontractor"
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// NEW: Discipline Donut Chart + Mini Trend
// =============================================================================
function DisciplineDonutChart({
  today,
  trend,
}: {
  today: WorkforceDisciplineTodaySummary | null;
  trend: WorkforceDisciplinePoint[];
}) {
  const hasData = today && today.total_direct > 0;

  if (!hasData) {
    return (
      <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-base font-medium">Direct Workforce by Discipline</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-16 text-sm text-muted-foreground">
          No direct workforce data
        </CardContent>
      </Card>
    );
  }

  const donutData = [
    { name: "Electrical", value: today.electrical, fill: COLOR_ELECTRICAL },
    { name: "Mechanical", value: today.mechanical, fill: COLOR_MECHANICAL },
    { name: "Civil", value: today.civil, fill: COLOR_CIVIL },
  ].filter((d) => d.value > 0);

  const trendData = trend.slice(-14).map((p) => ({
    date: p.snapshot_date.slice(5),
    electrical: p.electrical,
    mechanical: p.mechanical,
    civil: p.civil,
  }));

  return (
    <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">Direct Workforce by Discipline</CardTitle>
          <span className="text-xs text-muted-foreground tabular-nums">
            {today.total_direct} direct total
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Donut */}
          <div className="relative">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={donutData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  stroke="none"
                >
                  {donutData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value, name) => {
                    const numVal = Number(value);
                    const pct = today.total_direct > 0
                      ? ((numVal / today.total_direct) * 100).toFixed(0)
                      : "0";
                    return [`${value} (${pct}%)`, String(name)];
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* Center label */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center">
                <div className="text-2xl font-bold font-heading tabular-nums">{today.total_direct}</div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Direct</div>
              </div>
            </div>
          </div>

          {/* Legend + mini values */}
          <div className="flex flex-col justify-center gap-3">
            {donutData.map((d) => {
              const pct = today.total_direct > 0
                ? ((d.value / today.total_direct) * 100).toFixed(0)
                : "0";
              return (
                <div key={d.name} className="flex items-center gap-3">
                  <span
                    className="h-3 w-3 rounded-full shrink-0"
                    style={{ backgroundColor: d.fill }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{d.name}</div>
                    <div className="text-xs text-muted-foreground tabular-nums">
                      {d.value} ({pct}%)
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Mini trend sparkline */}
        {trendData.length > 1 && (
          <div className="mt-4 pt-4 border-t border-foreground/5">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
              14-Day Discipline Trend
            </div>
            <ResponsiveContainer width="100%" height={80}>
              <AreaChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <Area
                  type="monotone"
                  dataKey="electrical"
                  stackId="1"
                  stroke={COLOR_ELECTRICAL}
                  fill={COLOR_ELECTRICAL}
                  fillOpacity={0.3}
                  strokeWidth={1.5}
                />
                <Area
                  type="monotone"
                  dataKey="mechanical"
                  stackId="1"
                  stroke={COLOR_MECHANICAL}
                  fill={COLOR_MECHANICAL}
                  fillOpacity={0.3}
                  strokeWidth={1.5}
                />
                <Area
                  type="monotone"
                  dataKey="civil"
                  stackId="1"
                  stroke={COLOR_CIVIL}
                  fill={COLOR_CIVIL}
                  fillOpacity={0.3}
                  strokeWidth={1.5}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Top Positions (today) - horizontal bar
// =============================================================================
function TopPositionsChart({ positions }: { positions: WorkforceKPITopPosition[] }) {
  if (positions.length === 0) {
    return (
      <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-base font-medium">Top Positions Today</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-16 text-sm text-muted-foreground">
          No data
        </CardContent>
      </Card>
    );
  }

  const data = positions.map((p) => ({
    name: p.position_name.length > 24 ? p.position_name.slice(0, 24) + "..." : p.position_name,
    fullName: p.position_name,
    present: p.present,
    fill: CATEGORY_COLOR[p.category],
    category: p.category,
  }));

  return (
    <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-base font-medium">Top Positions Today</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={Math.max(220, data.length * 34)}>
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/30" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 11 }}
              width={160}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(value) => `${value} present`}
              labelFormatter={(_label, payload) => {
                const p = payload?.[0]?.payload;
                return p?.fullName ?? _label;
              }}
              contentStyle={tooltipStyle}
            />
            <Bar dataKey="present" radius={[0, 8, 8, 0]} barSize={22}>
              {data.map((entry, idx) => (
                <Cell key={idx} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Today by Category - vertical bars
// =============================================================================
function TodayByCategoryChart({ bundle }: { bundle: WorkforceKPIBundle }) {
  const data = bundle.by_category_today.map((c) => ({
    category: CATEGORY_LABEL[c.category],
    present: c.present_today,
    fill: CATEGORY_COLOR[c.category],
  }));

  if (data.length === 0 || data.every((d) => d.present === 0)) {
    return (
      <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-base font-medium">Today by Category</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-16 text-sm text-muted-foreground">
          No data
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-foreground/5 bg-card/60 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-base font-medium">Today by Category</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 5, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/30" vertical={false} />
            <XAxis dataKey="category" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
            <Tooltip
              formatter={(value) => `${value} present`}
              contentStyle={tooltipStyle}
            />
            <Bar dataKey="present" radius={[8, 8, 0, 0]} barSize={48}>
              {data.map((entry, idx) => (
                <Cell key={idx} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
