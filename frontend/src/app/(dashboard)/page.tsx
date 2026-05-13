"use client";

import { useEffect, useState } from "react";
import {
  Briefcase,
  Wallet,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Circle,
  Loader2,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api-client";
import type { Project } from "@/types/project";
import type { KPIMetric, DashboardStats } from "@/types/dashboard";
import { DailyBriefingCard } from "@/components/dashboard/daily-briefing-card";
import { DataQualityCard } from "@/components/dashboard/data-quality-card";

const kpiIcons = {
  active_projects: Briefcase,
  total_budget: Wallet,
  on_track: TrendingUp,
  open_risks: AlertTriangle,
} as const;

function KPICard({ metric, iconKey }: { metric: KPIMetric; iconKey: keyof typeof kpiIcons }) {
  const Icon = kpiIcons[iconKey];
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {metric.label}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold tracking-tight">{metric.value}</div>
        <p className="text-xs text-muted-foreground mt-1">{metric.change}</p>
      </CardContent>
    </Card>
  );
}

function KPISkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-4" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-8 w-16 mb-2" />
        <Skeleton className="h-3 w-20" />
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      try {
        const [statsResult, projectsResult] = await Promise.all([
          api.dashboard.stats(),
          api.projects.list(),
        ]);

        if (!cancelled) {
          setStats(statsResult);
          setProjects(projectsResult);
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Failed to load dashboard";
          setError(message);
        }
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, []);

  const isLoading = !stats && !projects && !error;
  const upcomingMilestones = projects?.filter((p) => p.status === "active").slice(0, 4) ?? [];

  return (
    <div className="space-y-6">
      {/* AI Daily Briefing — top of dashboard */}
      <DailyBriefingCard />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading || !stats ? (
          <>
            <KPISkeleton />
            <KPISkeleton />
            <KPISkeleton />
            <KPISkeleton />
          </>
        ) : (
          <>
            <KPICard metric={stats.active_projects} iconKey="active_projects" />
            <KPICard metric={stats.total_budget} iconKey="total_budget" />
            <KPICard metric={stats.on_track} iconKey="on_track" />
            <KPICard metric={stats.open_risks} iconKey="open_risks" />
          </>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Data Quality call-to-action: imported ledger rows missing
          budget code / subcontractor link */}
      <DataQualityCard />

      <Card>
        <CardHeader>
          <CardTitle>Active Projects</CardTitle>
          <CardDescription>Live from backend API</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : upcomingMilestones.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No active projects yet.</p>
          ) : (
            upcomingMilestones.map((p) => (
              <div key={p.id} className="flex items-start gap-3 text-sm">
                {p.health === "on_track" ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-500 mt-0.5 shrink-0" />
                ) : (
                  <Circle className="h-4 w-4 text-amber-600 dark:text-amber-500 mt-0.5 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-foreground font-medium truncate">{p.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {p.location} - {Number(p.progress_pct).toFixed(1)}% complete
                  </p>
                </div>
                <Badge
                  variant={p.health === "on_track" ? "secondary" : "outline"}
                  className="text-xs"
                >
                  {p.health === "on_track" ? "On track" : "At risk"}
                </Badge>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}


