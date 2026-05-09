"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Search, MoreHorizontal, Briefcase } from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { api } from "@/lib/api-client";
import type { Project, ProjectStatus, ProjectHealth } from "@/types/project";
import {
  formatRubCompact,
  formatLabel,
  formatPercent,
} from "@/lib/formatters";
import { useUser } from "@/components/providers/user-provider";
import { ProjectFormDialog } from "@/components/projects/project-form-dialog";

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

function getUtilizationBadge(pct: number | null): { label: string; className: string } {
  if (pct === null) {
    return { label: "—", className: "text-muted-foreground" };
  }
  if (pct === 0) {
    return { label: "0%", className: "bg-muted text-muted-foreground" };
  }
  if (pct < 80) {
    return {
      label: `${pct.toFixed(0)}%`,
      className: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400",
    };
  }
  if (pct <= 100) {
    return {
      label: `${pct.toFixed(0)}%`,
      className: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    };
  }
  return {
    label: `${pct.toFixed(0)}%`,
    className: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  };
}

export default function ProjectsPage() {
  const router = useRouter();
  const { user } = useUser();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [utilization, setUtilization] = useState<Record<number, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const canCreate = user?.role === "admin" || user?.role === "project_manager";
  const canDelete = user?.role === "admin";
  const canEdit = user?.role === "admin" || user?.role === "project_manager";

  async function loadProjects() {
    try {
      const data = await api.projects.list();
      setProjects(data);
      setError(null);

      // Fire off summary calls in parallel - don't block the table render
      data.forEach(async (p) => {
        try {
          const summary = await api.budgetItems.summaryForProject(p.id);
          setUtilization((prev) => ({ ...prev, [p.id]: summary.utilization_pct }));
        } catch {
          // Silently ignore per-project failures
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    }
  }

  useEffect(() => {
    loadProjects();
  }, []);

  const filtered = useMemo(() => {
    if (!projects) return [];
    const q = search.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.location.toLowerCase().includes(q) ||
        p.owner.full_name.toLowerCase().includes(q)
    );
  }, [projects, search]);

  const isLoading = projects === null && !error;

  function handleCreate() {
    setEditingProject(null);
    setFormOpen(true);
  }

  function handleEdit(project: Project) {
    setEditingProject(project);
    setFormOpen(true);
  }

  function handleViewBudget(project: Project) {
    router.push(`/projects/${project.id}/budget`);
  }

  function handleOpenProject(project: Project) {
    router.push(`/projects/${project.id}`);
  }

  async function handleConfirmDelete() {
    if (!deletingProject) return;
    setIsDeleting(true);
    try {
      await api.projects.delete(deletingProject.id);
      setDeletingProject(null);
      await loadProjects();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Projects</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your construction projects portfolio
          </p>
        </div>
        {canCreate && (
          <Button onClick={handleCreate}>
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Button>
        )}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-base font-medium">All Projects</CardTitle>
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search name, location..."
              className="pl-8"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {error && (
            <div className="px-6 py-4 text-sm text-destructive border-b border-destructive/20 bg-destructive/10">
              {error}
            </div>
          )}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[26%]">Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Health</TableHead>
                <TableHead>Location</TableHead>
                <TableHead className="text-right">Budget</TableHead>
                <TableHead className="text-center">Used</TableHead>
                <TableHead className="text-right">Progress</TableHead>
                <TableHead>Owner</TableHead>
                <TableHead className="w-[40px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 9 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 w-full" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="h-32 text-center">
                    <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground">
                      <Briefcase className="h-8 w-8" />
                      <p className="text-sm">
                        {search ? "No projects match your search." : "No projects yet."}
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((p) => {
                  const pct = utilization[p.id] ?? null;
                  const badge = getUtilizationBadge(pct);
                  return (
                    <TableRow
                      key={p.id}
                      className="cursor-pointer hover:bg-muted/40"
                      onClick={() => handleOpenProject(p)}
                    >
                      <TableCell className="font-medium">{p.name}</TableCell>
                      <TableCell>
                        <Badge variant={STATUS_VARIANT[p.status]} className="text-xs">
                          {formatLabel(p.status)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className={`text-xs font-medium ${HEALTH_COLOR[p.health]}`}>
                          {HEALTH_LABEL[p.health]}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {p.location}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {formatRubCompact(p.budget_rub)}
                      </TableCell>
                      <TableCell className="text-center">
                        <span
                          className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-sm">
                        {formatPercent(p.progress_pct)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {p.owner.full_name}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="h-4 w-4" />
                              <span className="sr-only">Actions</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleOpenProject(p)}>
                              Open Project
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleViewBudget(p)}>
                              View Budget
                            </DropdownMenuItem>
                            {canEdit && (
                              <DropdownMenuItem onClick={() => handleEdit(p)}>
                                Edit
                              </DropdownMenuItem>
                            )}
                            {canDelete && (
                              <DropdownMenuItem
                                onClick={() => setDeletingProject(p)}
                                className="text-destructive focus:text-destructive"
                              >
                                Delete
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <ProjectFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        project={editingProject}
        onSuccess={loadProjects}
      />

      <AlertDialog
        open={deletingProject !== null}
        onOpenChange={(open) => !open && setDeletingProject(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this project?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-foreground">
                {deletingProject?.name}
              </span>{" "}
              will be archived and removed from the list. This action can be reversed
              later from the database.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
