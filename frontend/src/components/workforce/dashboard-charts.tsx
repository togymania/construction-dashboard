"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
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
  WorkforceCategory,
} from "@/types/workforce";

// Indigo / cyan / emerald (matches theme accent triad)
const COLOR_DIRECT = "oklch(0.62 0.20 270)"; // indigo
const COLOR_INDIRECT = "oklch(0.70 0.15 200)"; // cyan
const COLOR_SUBCONTRACTOR = "oklch(0.68 0.18 155)"; // emerald

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

interface Props {
  kpis: WorkforceKPIBundle;
}

export function WorkforceDashboardCharts({ kpis }: Props) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TopPositionsChart positions={kpis.top_positions} />
        <TodayByCategoryChart bundle={kpis} />
      </div>

      <DailyTrendChart trend={kpis.daily_trend} />

      <WeeklyComparisonChart buckets={kpis.weekly_buckets} />
    </div>
  );
}

// =============================================================================
// Top Positions (today) - horizontal bar
// =============================================================================
function TopPositionsChart({ positions }: { positions: WorkforceKPITopPosition[] }) {
  if (positions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Top Positions Today</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-12 text-sm text-muted-foreground">
          No data
        </CardContent>
      </Card>
    );
  }

  // Truncate long position names for display
  const data = positions.map((p) => ({
    name: p.position_name.length > 28 ? p.position_name.slice(0, 28) + "..." : p.position_name,
    fullName: p.position_name,
    present: p.present,
    fill: CATEGORY_COLOR[p.category],
    category: p.category,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">Top Positions Today</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={Math.max(220, data.length * 32)}>
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 11 }}
              width={170}
            />
            <Tooltip
              formatter={(value) => `${value} present`}
              labelFormatter={(label, payload) => {
                const p = payload?.[0]?.payload;
                return p?.fullName ?? label;
              }}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="present" radius={[0, 6, 6, 0]}>
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
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Today by Category</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-12 text-sm text-muted-foreground">
          No data
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">Today by Category</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 5, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" />
            <XAxis dataKey="category" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              formatter={(value) => `${value} present`}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="present" radius={[8, 8, 0, 0]}>
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
// Daily Trend (last 30 days) - 3-series area chart
// =============================================================================
function DailyTrendChart({ trend }: { trend: WorkforceKPIDailyPoint[] }) {
  if (trend.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Daily Trend (last 30 days)</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-12 text-sm text-muted-foreground">
          No data
        </CardContent>
      </Card>
    );
  }

  const data = trend.map((p) => ({
    date: p.snapshot_date.slice(5),  // MM-DD only for x-axis
    fullDate: p.snapshot_date,
    direct: p.direct_present,
    indirect: p.indirect_present,
    subcontractor: p.subcontractor_present,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">
          Daily Trend (last {trend.length} {trend.length === 1 ? "day" : "days"})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data} margin={{ top: 10, right: 16, bottom: 5, left: 0 }}>
            <defs>
              <linearGradient id="grad-direct" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLOR_DIRECT} stopOpacity={0.7} />
                <stop offset="100%" stopColor={COLOR_DIRECT} stopOpacity={0.1} />
              </linearGradient>
              <linearGradient id="grad-indirect" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLOR_INDIRECT} stopOpacity={0.7} />
                <stop offset="100%" stopColor={COLOR_INDIRECT} stopOpacity={0.1} />
              </linearGradient>
              <linearGradient id="grad-sub" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLOR_SUBCONTRACTOR} stopOpacity={0.7} />
                <stop offset="100%" stopColor={COLOR_SUBCONTRACTOR} stopOpacity={0.1} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              labelFormatter={(label, payload) => {
                const p = payload?.[0]?.payload;
                return p?.fullDate ?? label;
              }}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend
              verticalAlign="top"
              height={28}
              iconType="circle"
              wrapperStyle={{ fontSize: 12 }}
            />
            <Area
              type="monotone"
              dataKey="direct"
              stackId="1"
              stroke={COLOR_DIRECT}
              fill="url(#grad-direct)"
              name="Direct"
            />
            <Area
              type="monotone"
              dataKey="indirect"
              stackId="1"
              stroke={COLOR_INDIRECT}
              fill="url(#grad-indirect)"
              name="Indirect"
            />
            <Area
              type="monotone"
              dataKey="subcontractor"
              stackId="1"
              stroke={COLOR_SUBCONTRACTOR}
              fill="url(#grad-sub)"
              name="Subcontractor"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Weekly Comparison (last 8 weeks) - bar chart
// =============================================================================
function WeeklyComparisonChart({ buckets }: { buckets: WorkforceKPIWeeklyBucket[] }) {
  if (buckets.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium">Weekly Comparison</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-12 text-sm text-muted-foreground">
          No data
        </CardContent>
      </Card>
    );
  }

  const data = buckets.map((b) => ({
    week: b.week_start.slice(5),  // MM-DD
    fullWeek: b.week_start,
    direct: Math.round(b.avg_direct),
    indirect: Math.round(b.avg_indirect),
    subcontractor: Math.round(b.avg_subcontractor),
    total: Math.round(b.avg_total_present),
    days: b.days_recorded,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">
          Weekly Average ({buckets.length} {buckets.length === 1 ? "week" : "weeks"})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 10, right: 16, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" />
            <XAxis dataKey="week" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              labelFormatter={(label, payload) => {
                const p = payload?.[0]?.payload;
                return p ? "Week of " + p.fullWeek + " (" + p.days + " days)" : label;
              }}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend verticalAlign="top" height={28} iconType="circle" wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="direct" stackId="a" fill={COLOR_DIRECT} name="Direct" radius={[0, 0, 0, 0]} />
            <Bar dataKey="indirect" stackId="a" fill={COLOR_INDIRECT} name="Indirect" />
            <Bar dataKey="subcontractor" stackId="a" fill={COLOR_SUBCONTRACTOR} name="Subcontractor" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
