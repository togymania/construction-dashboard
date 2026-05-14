"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Wallet,
  HardHat,
  Users,
  Receipt,
  Calendar,
  AlertTriangle,
  FileBarChart,
  MapPin,
  Building2,
  TrendingUp,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useProject } from "@/components/providers/project-provider";
import { useUser } from "@/components/providers/user-provider";
import { formatRubCompact, formatLabel, formatPercent } from "@/lib/formatters";
import type { ProjectStatus, ProjectHealth } from "@/types/project";
import { EACWidget } from "@/components/projects/eac-widget";

const STATUS_VARIANT: Record<ProjectStatus, "default" | "secondary" | "outline"> = {
  planning: "outline",
  active: "default",
  on_hold: "secondary",
  completed: "secondary",
  cancelled: "outline",
};

const HEALTH_LABEL: Record<ProjectHealth, string> = {
  on_track: "On track",
  at_risk: "At risk",
  delayed: "Delayed",
};

const HEALTH_COLOR: Record<ProjectHealth, string> = {
  on_track: "text-green-600 dark:text-green-500",
  at_risk: "text-amber-600 dark:text-amber-500",
  delayed: "text-red-600 dark:text-red-500",
};

const MODULES = [
  {
    segment: "subcontractors",
    title: "Subcontractors",
    description: "Companies, contracts and payments",
    icon: HardHat,
  },
  {
    segment: "workforce",
    title: "Workforce",
    description: "Daily puantaj, productivity, trends",
    icon: Users,
  },
  {
    segment: "budget",
    title: "Budget",
    description: "Categories, items, planned vs actual",
    icon: Wallet,
  },
  {
    segment: "expenses",
    title: "Expenses",
    description: "Income & expense ledger imported from Excel",
    icon: Receipt,
  },
  {
    segment: "schedule",
    title: "Schedule",
    description: "Timeline, milestones, dependencies",
    icon: Calendar,
  },
  {
    segment: "risks",
    title: "Risks",
    description: "AI-detected risks & mitigation plans",
    icon: AlertTriangle,
  },
  {
    segment: "reports",
    title: "Reports",
    description: "Executive summary & exports",
    icon: FileBarChart,
  },
];

export default function ProjectOverviewPage() {
  const { project, isLoading, error } = useProject();
  const { user } = useUser();
  const router = useRouter();

  // WORKFORCE_EDITOR proje genel bakışını göremez — otomatik olarak
  // İşgücü sekmesine yönlendiriyoruz.
  useEffect(() => {
    if (user?.role === "workforce_editor" && project?.id) {
      router.replace(`/projects/${project.id}/workforce`);
    }
  }, [user?.role, project?.id, router]);

  // Modules grid yalnız diğer roller için kullanılır; WORKFORCE_EDITOR
  // redirect'ten önce kısa bir an sayfayı görse de "Workforce" tek kart
  // olarak çıksın.
  const visibleModules = user?.role === "workforce_editor"
    ? MODULES.filter((m) => m.segment === "workforce")
    : MODULES;

  if (error) {
    return (
      <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (isLoading || !project) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-32 w-full" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Project header card */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2 min-w-0">
              <div className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-muted-foreground shrink-0" />
                <h1 className="text-2xl font-semibold tracking-tight truncate">
                  {project.name}
                </h1>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {project.location}
                </span>
                <Badge variant={STATUS_VARIANT[project.status]} className="text-xs">
                  {formatLabel(project.status)}
                </Badge>
                <span className={`text-xs font-medium ${HEALTH_COLOR[project.health]}`}>
                  {HEALTH_LABEL[project.health]}
                </span>
              </div>
              {project.description && (
                <p className="text-sm text-muted-foreground max-w-3xl pt-1">
                  {project.description}
                </p>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">
                Budget
              </p>
              <p className="text-xl font-bold mt-1">
                {formatRubCompact(project.budget_rub)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">
                Progress
              </p>
              <p className="text-xl font-bold mt-1 inline-flex items-center gap-1">
                <TrendingUp className="h-4 w-4 text-primary" />
                {formatPercent(project.progress_pct)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">
                Start date
              </p>
              <p className="text-xl font-bold mt-1">
                {new Date(project.start_date).toLocaleDateString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">
                End date
              </p>
              <p className="text-xl font-bold mt-1">
                {new Date(project.end_date).toLocaleDateString()}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Earned-Value forecast — bütçe aşımını önceden yakalayan EAC widget */}
      <EACWidget projectId={project.id} />

      {/* Module quick-launch grid */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          Modules
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {visibleModules.map((m) => {
            const Icon = m.icon;
            return (
              <Link key={m.segment} href={`/projects/${project.id}/${m.segment}`}>
                <Card className="hover:shadow-lg hover:border-primary/40 transition-all duration-300 cursor-pointer h-full">
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 border border-primary/20">
                        <Icon className="h-4 w-4 text-primary" />
                      </div>
                      <CardTitle className="text-base">{m.title}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-xs leading-relaxed">
                      {m.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
