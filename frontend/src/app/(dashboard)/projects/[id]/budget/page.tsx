"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Plus,
  Upload,
  MoreHorizontal,
  Wallet,
  ArrowLeft,
  TrendingUp,
  AlertCircle,
  FileSpreadsheet,
  Trash2,
  Pencil,
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { api } from "@/lib/api-client";
import {
  formatRub,
  formatRubCompact,
  formatPercent,
  formatDate,
} from "@/lib/formatters";
import type { Project } from "@/types/project";
import type {
  BudgetCategory,
  BudgetItem,
  BudgetSummary,
  Expense,
} from "@/types/budget";
import { useUser } from "@/components/providers/user-provider";
import { BudgetItemFormDialog } from "@/components/budget-items/budget-item-form-dialog";
import { BudgetItemImportDialog } from "@/components/budget-items/budget-item-import-dialog";
import { ExpenseFormDialog } from "@/components/expenses/expense-form-dialog";
import { ExpenseImportDialog } from "@/components/expenses/expense-import-dialog";

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
  const [categories, setCategories] = useState<BudgetCategory[]>([]);
  const [expenses, setExpenses] = useState<Expense[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Budget Item dialogs
  const [formOpen, setFormOpen] = useState(false);
  const [itemImportOpen, setItemImportOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<BudgetItem | null>(null);
  const [deletingItem, setDeletingItem] = useState<BudgetItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Expense dialogs
  const [expenseFormOpen, setExpenseFormOpen] = useState(false);
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null);
  const [deletingExpense, setDeletingExpense] = useState<Expense | null>(null);
  const [isDeletingExpense, setIsDeletingExpense] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);

  // Expense filters
  const [filterCategoryId, setFilterCategoryId] = useState<string>("all");

  const canManage = user?.role === "admin" || user?.role === "project_manager";

  async function loadAll() {
    if (isNaN(projectId)) return;
    try {
      const [proj, itemList, summ, cats, expList] = await Promise.all([
        api.projects.get(projectId),
        api.budgetItems.listForProject(projectId),
        api.budgetItems.summaryForProject(projectId),
        api.budgetCategories.list(),
        api.expenses.listForProject(projectId),
      ]);
      setProject(proj);
      setItems(itemList);
      setSummary(summ);
      setCategories(cats);
      setExpenses(expList);
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

  // ---- Budget Items: grouped by category ----
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

  // ---- Expenses: filtered ----
  const filteredExpenses = useMemo(() => {
    if (!expenses) return [];
    if (filterCategoryId === "all") return expenses;
    return expenses.filter((e) => e.category_id === parseInt(filterCategoryId, 10));
  }, [expenses, filterCategoryId]);

  const expenseTotalFiltered = useMemo(
    () => filteredExpenses.reduce((sum, e) => sum + parseFloat(e.amount), 0),
    [filteredExpenses]
  );

  // ---- Budget Item handlers ----
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

  // ---- Expense handlers ----
  function handleCreateExpense() {
    setEditingExpense(null);
    setExpenseFormOpen(true);
  }

  function handleEditExpense(expense: Expense) {
    setEditingExpense(expense);
    setExpenseFormOpen(true);
  }

  async function handleConfirmDeleteExpense() {
    if (!deletingExpense) return;
    setIsDeletingExpense(true);
    try {
      await api.expenses.delete(projectId, deletingExpense.id);
      setDeletingExpense(null);
      await loadAll();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setIsDeletingExpense(false);
    }
  }

  // ---- Charts ----
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

  // ---- Render ----

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
        </div>
      </div>

      {/* KPI Cards */}
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
              {expenses?.length ?? 0} expense records
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

      {/* Charts */}
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

      {/* Tabs: Budget Items | Expenses */}
      <Tabs defaultValue="budget-items" className="space-y-4">
        <TabsList>
          <TabsTrigger value="budget-items">
            Budget Items
            {items && items.length > 0 && (
              <Badge variant="secondary" className="ml-2 text-xs">
                {items.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="expenses">
            Expenses
            {expenses && expenses.length > 0 && (
              <Badge variant="secondary" className="ml-2 text-xs">
                {expenses.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* ===== Budget Items Tab ===== */}
        <TabsContent value="budget-items">
          <Card>
            <CardHeader className="pb-4 flex flex-row items-center justify-between">
              <CardTitle className="text-base font-medium">Budget Items</CardTitle>
              {canManage && (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setItemImportOpen(true)}
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    Import
                  </Button>
                  <Button size="sm" onClick={handleCreate}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Budget Item
                  </Button>
                </div>
              )}
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
                      <Fragment key={`group-${group.categoryId}`}>
                        <TableRow className="bg-muted/30 hover:bg-muted/30">
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
                      </Fragment>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===== Expenses Tab ===== */}
        <TabsContent value="expenses">
          <Card>
            <CardHeader className="pb-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <CardTitle className="text-base font-medium">Expenses</CardTitle>
                <div className="flex items-center gap-2">
                  {/* Category filter */}
                  <Select value={filterCategoryId} onValueChange={setFilterCategoryId}>
                    <SelectTrigger className="w-[180px] h-9 text-sm">
                      <SelectValue placeholder="All categories" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Categories</SelectItem>
                      {categories
                        .filter((c) => c.is_active)
                        .map((cat) => (
                          <SelectItem key={cat.id} value={String(cat.id)}>
                            {cat.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>

                  {canManage && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setImportDialogOpen(true)}
                      >
                        <FileSpreadsheet className="mr-2 h-4 w-4" />
                        Import Excel
                      </Button>
                      <Button size="sm" onClick={handleCreateExpense}>
                        <Plus className="mr-2 h-4 w-4" />
                        Add Expense
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {expenses === null ? (
                <div className="px-6 py-4">
                  <Skeleton className="h-32 w-full" />
                </div>
              ) : filteredExpenses.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground">
                  <Wallet className="h-8 w-8" />
                  <p className="text-sm">
                    {expenses.length === 0
                      ? "No expenses recorded yet."
                      : "No expenses match the selected filter."}
                  </p>
                  {canManage && expenses.length === 0 && (
                    <div className="flex gap-2 mt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setImportDialogOpen(true)}
                      >
                        <FileSpreadsheet className="mr-2 h-4 w-4" />
                        Import from Excel
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCreateExpense}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Add manually
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Vendor</TableHead>
                        <TableHead>Invoice #</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead className="text-right">Amount</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead className="w-[40px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredExpenses.map((exp) => (
                        <TableRow key={exp.id}>
                          <TableCell className="font-medium">
                            {exp.vendor || "-"}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {exp.invoice_number || "-"}
                          </TableCell>
                          <TableCell className="max-w-[200px] truncate">
                            {exp.description}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">
                              {exp.category.name}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right tabular-nums font-medium">
                            {formatRub(exp.amount)}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                            {formatDate(exp.expense_date)}
                          </TableCell>
                          <TableCell>
                            {canManage && (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon" className="h-8 w-8">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => handleEditExpense(exp)}>
                                    <Pencil className="mr-2 h-4 w-4" />
                                    Edit
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onClick={() => setDeletingExpense(exp)}
                                    className="text-destructive focus:text-destructive"
                                  >
                                    <Trash2 className="mr-2 h-4 w-4" />
                                    Delete
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {/* Total bar */}
                  <div className="flex items-center justify-between px-6 py-3 border-t bg-muted/30">
                    <span className="text-sm text-muted-foreground">
                      {filteredExpenses.length} expense{filteredExpenses.length !== 1 ? "s" : ""}
                      {filterCategoryId !== "all" ? " (filtered)" : ""}
                    </span>
                    <span className="font-semibold tabular-nums">
                      {formatRub(expenseTotalFiltered)}
                    </span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ===== Dialogs ===== */}

      {/* Budget Item Form */}
      <BudgetItemFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        projectId={projectId}
        item={editingItem}
        onSuccess={loadAll}
      />

      {/* Budget Item Excel Import */}
      <BudgetItemImportDialog
        open={itemImportOpen}
        onOpenChange={setItemImportOpen}
        projectId={projectId}
        onSuccess={loadAll}
      />

      {/* Budget Item Delete Confirm */}
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

      {/* Expense Form */}
      <ExpenseFormDialog
        open={expenseFormOpen}
        onOpenChange={setExpenseFormOpen}
        projectId={projectId}
        expense={editingExpense}
        categories={categories}
        budgetItems={items ?? []}
        onSuccess={loadAll}
      />

      {/* Expense Import */}
      <ExpenseImportDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        projectId={projectId}
        categories={categories}
        onSuccess={loadAll}
      />

      {/* Expense Delete Confirm */}
      <AlertDialog
        open={deletingExpense !== null}
        onOpenChange={(open) => !open && setDeletingExpense(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this expense?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-foreground">
                {deletingExpense?.description}
              </span>
              {deletingExpense?.vendor && (
                <>
                  {" "}from{" "}
                  <span className="font-medium text-foreground">
                    {deletingExpense.vendor}
                  </span>
                </>
              )}{" "}
              ({formatRub(deletingExpense?.amount)}) will be permanently removed.
              This will update the budget summary.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletingExpense}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDeleteExpense}
              disabled={isDeletingExpense}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeletingExpense ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
