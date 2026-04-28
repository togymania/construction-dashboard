"use client";

import { useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRubCompact } from "@/lib/formatters";
import type { SubcontractorKPIs } from "@/types/subcontractor";

// Shared color palette — matches budget/page.tsx convention
const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

// Per-status semantic colors (overrides PIE_COLORS for status-bound charts)
const PAYMENT_STATUS_COLORS: Record<string, string> = {
  pending: "#f59e0b",   // amber
  approved: "#3b82f6",  // blue
  paid: "#10b981",      // emerald
  rejected: "#ef4444",  // red
};

const CONTRACT_STATUS_COLORS: Record<string, string> = {
  draft: "#94a3b8",     // slate-400
  active: "#3b82f6",    // blue
  completed: "#10b981", // emerald
  terminated: "#ef4444",// red
};

function prettify(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

interface Props {
  kpis: SubcontractorKPIs | null;
}

export function KpiCharts({ kpis }: Props) {
  // Hooks must be called unconditionally — compute even when kpis is null.
  // We use empty arrays/objects as safe fallbacks.

  // Payments by status: { pending: "150000000.00", paid: "...", ... } -> chart data
  const paymentsData = useMemo(() => {
    if (!kpis) return [];
    return Object.entries(kpis.payments_by_status)
      .map(([status, amount]) => ({
        name: prettify(status),
        rawStatus: status,
        value: parseFloat(amount),
      }))
      .filter((d) => d.value > 0);
  }, [kpis]);

  const contractsData = useMemo(() => {
    if (!kpis) return [];
    return Object.entries(kpis.contracts_by_status)
      .map(([status, count]) => ({
        name: prettify(status),
        rawStatus: status,
        value: count,
      }))
      .filter((d) => d.value > 0);
  }, [kpis]);

  const topSubsData = useMemo(() => {
    if (!kpis) return [];
    return kpis.top_subcontractors.slice(0, 5).map((s) => ({
      name: s.name.length > 18 ? s.name.slice(0, 16) + "..." : s.name,
      fullName: s.name,
      value: parseFloat(s.total_value),
      contracts: s.contract_count,
    }));
  }, [kpis]);

  // Monthly payments: backend returns {month: "YYYY-MM", amount: "...", count}
  // Show last 6 months for readability.
  const monthlyData = useMemo(() => {
    if (!kpis) return [];
    return kpis.monthly_payments.slice(-6).map((p) => {
      // "2024-05" -> "May 24"
      const [year, month] = p.month.split("-");
      const monthNames = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
      ];
      const m = parseInt(month, 10) - 1;
      const label = `${monthNames[m] ?? month} ${year.slice(2)}`;
      return {
        month: label,
        amount: parseFloat(p.amount),
        count: p.count,
      };
    });
  }, [kpis]);

  if (kpis === null) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-40" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-64 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* 1. Payments by Status — Pie */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Payments by Status</CardTitle>
        </CardHeader>
        <CardContent>
          {paymentsData.length === 0 ? (
            <EmptyChart label="No payment data yet" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={paymentsData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="45%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={2}
                  label={(entry) => {
                    const pct = (entry.percent ?? 0) * 100;
                    return pct >= 6 ? `${pct.toFixed(0)}%` : "";
                  }}
                  labelLine={false}
                >
                  {paymentsData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        PAYMENT_STATUS_COLORS[entry.rawStatus] ??
                        PIE_COLORS[index % PIE_COLORS.length]
                      }
                      stroke="transparent"
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: unknown) =>
                    typeof v === "number" ? formatRubCompact(v) : String(v)
                  }
                />
                <Legend
                  verticalAlign="bottom"
                  iconType="circle"
                  wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* 2. Top 5 Subcontractors — Bar */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Top 5 Subcontractors by Value</CardTitle>
        </CardHeader>
        <CardContent>
          {topSubsData.length === 0 ? (
            <EmptyChart label="No subcontractors yet" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topSubsData} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  type="number"
                  tickFormatter={(v) => formatRubCompact(v)}
                  className="text-xs"
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  className="text-xs"
                  width={120}
                />
                <Tooltip
                  formatter={(v: unknown) =>
                    typeof v === "number" ? formatRubCompact(v) : String(v)
                  }
                  labelFormatter={(label, payload) => {
                    const p = payload?.[0]?.payload as { fullName?: string } | undefined;
                    return p?.fullName ?? label;
                  }}
                />
                <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* 3. Monthly Payments Trend — Area */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Monthly Payments (Last 6 Months)</CardTitle>
        </CardHeader>
        <CardContent>
          {monthlyData.length === 0 ? (
            <EmptyChart label="No payment history yet" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={monthlyData}>
                <defs>
                  <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="month" className="text-xs" />
                <YAxis
                  tickFormatter={(v) => formatRubCompact(v)}
                  className="text-xs"
                />
                <Tooltip
                  formatter={(v: unknown) =>
                    typeof v === "number" ? formatRubCompact(v) : String(v)
                  }
                />
                <Area
                  type="monotone"
                  dataKey="amount"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorAmount)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* 4. Contracts by Status — Donut */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Contracts by Status</CardTitle>
        </CardHeader>
        <CardContent>
          {contractsData.length === 0 ? (
            <EmptyChart label="No contracts yet" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={contractsData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="45%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={2}
                  label={(entry) => {
                    const pct = (entry.percent ?? 0) * 100;
                    return pct >= 8 ? `${entry.value}` : "";
                  }}
                  labelLine={false}
                >
                  {contractsData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        CONTRACT_STATUS_COLORS[entry.rawStatus] ??
                        PIE_COLORS[index % PIE_COLORS.length]
                      }
                      stroke="transparent"
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend
                  verticalAlign="bottom"
                  iconType="circle"
                  wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">
      {label}
    </div>
  );
}
