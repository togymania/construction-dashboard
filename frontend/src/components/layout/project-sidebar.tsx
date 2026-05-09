"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  HardHat,
  Users,
  Receipt,
  Calendar,
  AlertTriangle,
  FileBarChart,
  Wallet,
  ChevronLeft,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { useProject } from "@/components/providers/project-provider";
import { useT } from "@/lib/i18n/provider";

interface NavItem {
  tKey: string;
  fallback: string;
  segment: string;
  icon: React.ComponentType<{ className?: string }>;
}

// Module pages live under /projects/[id]/<segment>.
// Order matches reading order in the daily standup: status → people →
// money → time → risk → output.
const PROJECT_NAV: NavItem[] = [
  { tKey: "nav.overview", fallback: "Overview", segment: "", icon: LayoutDashboard },
  { tKey: "nav.subcontractors", fallback: "Subcontractors", segment: "subcontractors", icon: HardHat },
  { tKey: "nav.workforce", fallback: "Workforce", segment: "workforce", icon: Users },
  { tKey: "nav.budget", fallback: "Budget", segment: "budget", icon: Wallet },
  { tKey: "nav.expenses", fallback: "Expenses", segment: "expenses", icon: Receipt },
  { tKey: "nav.schedule", fallback: "Schedule", segment: "schedule", icon: Calendar },
  { tKey: "nav.risks", fallback: "Risks", segment: "risks", icon: AlertTriangle },
  { tKey: "nav.reports", fallback: "Reports", segment: "reports", icon: FileBarChart },
];

interface Props {
  projectId: number;
  className?: string;
}

export function ProjectSidebar({ projectId, className }: Props) {
  const pathname = usePathname();
  const { project, isLoading } = useProject();
  const { t } = useT();

  const baseHref = `/projects/${projectId}`;

  return (
    <aside
      className={cn(
        "flex h-full w-60 flex-col border-r bg-sidebar text-sidebar-foreground",
        className
      )}
    >
      {/* Project header */}
      <div className="border-b px-4 py-4 space-y-2">
        <Link
          href="/projects"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronLeft className="h-3 w-3" />
          {t("project.backToProjects") || "All projects"}
        </Link>
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        ) : project ? (
          <div className="space-y-1">
            <h2 className="font-semibold text-sm leading-tight tracking-tight line-clamp-2">
              {project.name}
            </h2>
            <p className="text-[11px] text-muted-foreground truncate">
              {project.location}
            </p>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Project</p>
        )}
      </div>

      {/* Module nav */}
      <nav className="flex-1 space-y-1 p-3 overflow-y-auto">
        {PROJECT_NAV.map((item) => {
          const href = item.segment ? `${baseHref}/${item.segment}` : baseHref;
          const isActive =
            item.segment === ""
              ? pathname === baseHref
              : pathname === href || pathname.startsWith(href + "/");
          const Icon = item.icon;

          return (
            <Link
              key={item.segment || "overview"}
              href={href}
              className={cn(
                "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all duration-300",
                "before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:rounded-r-full before:transition-all before:duration-300",
                isActive
                  ? "bg-primary/10 text-foreground before:h-6 before:w-[3px] before:bg-primary before:shadow-[0_0_12px_rgba(99,102,241,0.6)]"
                  : "text-muted-foreground hover:bg-primary/5 hover:text-foreground before:h-0 before:w-[3px] before:bg-transparent"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 transition-colors duration-300",
                  isActive && "text-primary"
                )}
              />
              {t(item.tKey) || item.fallback}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
