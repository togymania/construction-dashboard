"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Plus,
  MoreHorizontal,
  Wallet,
  ArrowLeft,
  TrendingUp,
  AlertCircle,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { formatRub, formatRubCompact, formatPercent } from "@/lib/formatters";
import type { Project } from "@/types/project";
import type { BudgetItem, BudgetSummary } from "@/types/budget";
import { useUser } from "@/components/providers/user-provider";
import { BudgetItemFormDialog } from "@/components/budget-items/budget-item-form-dialog";

const CHART_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#ef4444",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
];

export default function ProjectBudgetPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useUser();
  const projectId = parseInt(params.id as string, 10);

  const [project, setProject] = useState<Project | null>(null);
  const [items, setItems] = useState<BudgetItem[] | null>(null);
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<BudgetItem | null>(null);
  const [deletingItem, setDeletingItem] = useState<BudgetItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const canManage = user?.role === "admin" || user?.role === "project_manager";

  async function loadAll() {
    if (isNaN(projectId)) return;
    try {
      const [proj, itemList, summ] = await Promise.all([
        api.projects.get(projectId),
        api.budgetItems.listForProject(projectId),
        api.budgetItems.summaryForProject(projectId),
      ]);
      setProject(proj);
      setItems(itemList);
      setSummary(summ);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load budget");
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const isLoading = project === null && items === null && !error;

  const groupedItems = useMemo(() => {
    if (!items) return [];
    const groups = new Map<number, { categoryName: string; items: BudgetItem[] }>();
    for (const item of items) {
      const existing = groups.get(item.category_id);
      if (existing) {
        existing.items.push(item);
      } else {
        groups.set(item.category_id, {
          categoryName: item.category.name,
          items: [item],
        });
      }
    }
    return Array.from(groups.entries()).map(([categoryId, group]) => ({
      categoryId,
      categoryName: group.categoryName,
      items: group.items,
      subtotal: group.items.reduce((sum, i) => sum + parseFloat(i.planned_amount), 0),
    }));
  }, [items]);

  function handleCreate() {
    setEditingItem(null);
    setFormOpen(true);
  }

  function handleEdit(item: BudgetItem) {
    setEditingItem(item);
    setFormOpen(true);
  }

  async function handleConfirmDelete() {
    if (!deletingItem) return;
    setIsDeleting(true);
    try {
      await api.budgetItems.delete(deletingItem.id);
      setDeletingItem(null);
      await loadAll();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setIsDeleting(false);
    }
  }

  const pieData = useMemo(() => {
    if (!summary) return [];
    return summary.by_category.map((c) => ({
      name: c.category_name,
      value: parseFloat(c.planned_amount),
    }));
  }, [summary]);

  const barData = useMemo(() => {
    if (!summary) return [];
    return summary.by_category.map((c) => ({
      name: c.category_name,
      Planned: parseFloat(c.planned_amount),
      Spent: parseFloat(c.spent_amount),
    }));
  }, [summary]);

  const utilizationPct = summary?.utilization_pct ?? 0;
  const utilizationColor =
    utilizationPct < 80
      ? "text-green-600 dark:text-green-500"
      : utilizationPct < 100
      ? "text-amber-600 dark:text-amber-500"
      : "text-red-600 dark:text-red-500";

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-96 rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => router.push("/projects")}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to projects
        </Button>
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
            <AlertCircle className="h-8 w-8" />
            <p className="text-sm">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" onClick={() => router.push("/projects")}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to projects
        </Button>
        <div className="flex items-center justify-between gap-4 mt-2">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">{project?.name}</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {project?.location} &middot; Budget breakdown
            </p>
          </div>
          {canManage && (
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Add Budget Item
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Project Budget
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {formatRubCompact(project?.budget_rub)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Approved cap</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Total Planned
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {formatRubCompact(summary?.total_planned)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Across {items?.length ?? 0} line items
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Total Spent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {formatRubCompact(summary?.total_spent)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              + {formatRubCompact(summary?.total_pending)} pending
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Utilization
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-semibold ${utilizationColor}`}>
              {formatPercent(utilizationPct)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {formatRubCompact(summary?.remaining)} remaining
            </p>
          </CardContent>
        </Card>
      </div>

      {summary && summary.by_category.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">Planned by Category</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={({ name, percent }) =>
                      `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                    }
                    labelLine={false}
                  >
                    {pieData.map((_, idx) => (
                      <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number) => formatRub(value)}
                    contentStyle={{ fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base font-medium">Planned vs Spent</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={barData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11 }}
                    interval={0}
                    angle={-15}
                    textAnchor="end"
                    height={50}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: number) => formatRubCompact(v)}
                  />
                  <Tooltip
                    formatter={(value: number) => formatRub(value)}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Planned" fill="#3b82f6" />
                  <Bar dataKey="Spent" fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-medium">Budget Items</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {items === null ? (
            <div className="px-6 py-4">
              <Skeleton className="h-32 w-full" />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground">
              <Wallet className="h-8 w-8" />
              <p className="text-sm">No budget items yet.</p>
              {canManage && (
                <Button variant="outline" size="sm" onClick={handleCreate} className="mt-2">
                  <Plus className="mr-2 h-4 w-4" /> Add the first one
                </Button>
              )}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead className="w-[120px]">Notes</TableHead>
                  <TableHead className="text-right w-[200px]">Planned Amount</TableHead>
                  <TableHead className="w-[40px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {groupedItems.map((group) => (
                  <>
                    <TableRow key={`group-${group.categoryId}`} className="bg-muted/30 hover:bg-muted/30">
                      <TableCell colSpan={2} className="font-semibold text-xs uppercase tracking-wider text-muted-foreground py-2">
                        {group.categoryName}
                      </TableCell>
                      <TableCell className="text-right font-semibold text-sm py-2">
                        {formatRub(group.subtotal)}
                      </TableCell>
                      <TableCell className="py-2"></TableCell>
                    </TableRow>
                    {group.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium pl-8">{item.description}</TableCell>
                        <TableCell className="text-xs text-muted-foreground truncate max-w-[120px]">
                          {item.notes || "-"}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatRub(item.planned_amount)}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              {canManage ? (
                                <>
                                  <DropdownMenuItem onClick={() => handleEdit(item)}>
                                    Edit
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onClick={() => setDeletingItem(item)}
                                    className="text-destructive focus:text-destructive"
                                  >
                                    Delete
                                  </DropdownMenuItem>
                                </>
                              ) : (
                                <DropdownMenuItem disabled>No actions available</DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <BudgetItemFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        projectId={projectId}
        item={editingItem}
        onSuccess={loadAll}
      />

      <AlertDialog
        open={deletingItem !== null}
        onOpenChange={(open) => !open && setDeletingItem(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this budget item?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-foreground">
                {deletingItem?.description}
              </span>{" "}
              will be permanently removed. Linked expenses will keep their amounts but
              lose the connection to this line item.
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
