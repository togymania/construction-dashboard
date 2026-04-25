"use client";

import { useEffect, useState } from "react";
import { Plus, MoreHorizontal, Tags, ArrowUp, ArrowDown, Lock } from "lucide-react";

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
import type { BudgetCategory } from "@/types/budget";
import { useUser } from "@/components/providers/user-provider";
import { CategoryFormDialog } from "@/components/budget-categories/category-form-dialog";

export default function BudgetCategoriesPage() {
  const { user } = useUser();
  const [categories, setCategories] = useState<BudgetCategory[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<BudgetCategory | null>(null);
  const [deletingCategory, setDeletingCategory] = useState<BudgetCategory | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [reorderingId, setReorderingId] = useState<number | null>(null);

  const canManage = user?.role === "admin" || user?.role === "project_manager";
  const canDelete = user?.role === "admin";

  async function loadCategories() {
    try {
      const data = await api.budgetCategories.list(true); // include inactive
      setCategories(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load categories");
    }
  }

  useEffect(() => {
    loadCategories();
  }, []);

  const isLoading = categories === null && !error;

  function handleCreate() {
    setEditingCategory(null);
    setFormOpen(true);
  }

  function handleEdit(category: BudgetCategory) {
    setEditingCategory(category);
    setFormOpen(true);
  }

  async function handleConfirmDelete() {
    if (!deletingCategory) return;
    setIsDeleting(true);
    try {
      await api.budgetCategories.delete(deletingCategory.id);
      setDeletingCategory(null);
      await loadCategories();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleMove(category: BudgetCategory, direction: "up" | "down") {
    if (!categories) return;
    const idx = categories.findIndex((c) => c.id === category.id);
    if (idx === -1) return;

    const targetIdx = direction === "up" ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= categories.length) return;

    const newOrder = [...categories];
    [newOrder[idx], newOrder[targetIdx]] = [newOrder[targetIdx], newOrder[idx]];

    setReorderingId(category.id);
    try {
      const updated = await api.budgetCategories.reorder(newOrder.map((c) => c.id));
      setCategories(updated);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Reorder failed");
    } finally {
      setReorderingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Budget Categories</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage the categories used to organize budget items and expenses across all projects.
          </p>
        </div>
        {canManage && (
          <Button onClick={handleCreate}>
            <Plus className="mr-2 h-4 w-4" />
            New Category
          </Button>
        )}
      </div>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-medium">All Categories</CardTitle>
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
                <TableHead className="w-[50px]">Order</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Slug</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                {canManage && <TableHead className="w-[100px] text-right">Reorder</TableHead>}
                <TableHead className="w-[40px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: canManage ? 7 : 6 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton className="h-4 w-full" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : !categories || categories.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={canManage ? 7 : 6} className="h-32 text-center">
                    <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground">
                      <Tags className="h-8 w-8" />
                      <p className="text-sm">No categories yet.</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                categories.map((c, idx) => (
                  <TableRow key={c.id} className={!c.is_active ? "opacity-60" : undefined}>
                    <TableCell className="text-sm text-muted-foreground tabular-nums">
                      {c.display_order}
                    </TableCell>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {c.name}
                        {c.is_system && <Lock className="h-3 w-3 text-muted-foreground" />}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {c.slug}
                    </TableCell>
                    <TableCell>
                      {c.is_system ? (
                        <Badge variant="secondary" className="text-xs">System</Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs">Custom</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={c.is_active ? "default" : "outline"}
                        className="text-xs"
                      >
                        {c.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    {canManage && (
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            disabled={idx === 0 || reorderingId !== null}
                            onClick={() => handleMove(c, "up")}
                          >
                            <ArrowUp className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            disabled={idx === categories.length - 1 || reorderingId !== null}
                            onClick={() => handleMove(c, "down")}
                          >
                            <ArrowDown className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    )}
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Actions</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          {canManage && (
                            <DropdownMenuItem onClick={() => handleEdit(c)}>
                              Edit
                            </DropdownMenuItem>
                          )}
                          {canDelete && !c.is_system && (
                            <DropdownMenuItem
                              onClick={() => setDeletingCategory(c)}
                              className="text-destructive focus:text-destructive"
                            >
                              Delete
                            </DropdownMenuItem>
                          )}
                          {canDelete && c.is_system && (
                            <DropdownMenuItem disabled>
                              Cannot delete system category
                            </DropdownMenuItem>
                          )}
                          {!canManage && !canDelete && (
                            <DropdownMenuItem disabled>No actions available</DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <CategoryFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        category={editingCategory}
        onSuccess={loadCategories}
      />

      <AlertDialog
        open={deletingCategory !== null}
        onOpenChange={(open) => !open && setDeletingCategory(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this category?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-foreground">
                {deletingCategory?.name}
              </span>{" "}
              will be permanently removed. This action will fail if any budget
              items or expenses still reference this category.
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
