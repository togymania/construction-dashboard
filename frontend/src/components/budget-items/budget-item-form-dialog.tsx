"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { api } from "@/lib/api-client";
import {
  budgetItemFormSchema,
  type BudgetItemFormInput,
} from "@/lib/validators/budget-item-schema";
import type { BudgetCategory, BudgetItem } from "@/types/budget";

interface BudgetItemFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: number;
  item?: BudgetItem | null;
  onSuccess: () => void;
}

export function BudgetItemFormDialog({
  open,
  onOpenChange,
  projectId,
  item,
  onSuccess,
}: BudgetItemFormDialogProps) {
  const isEdit = Boolean(item);
  const [categories, setCategories] = useState<BudgetCategory[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<BudgetItemFormInput>({
    resolver: zodResolver(budgetItemFormSchema),
    defaultValues: {
      category_id: 0,
      description: "",
      planned_amount: 0,
      notes: "",
    },
  });

  const categoryValue = watch("category_id");

  useEffect(() => {
    if (!open) return;

    setLoadingCategories(true);
    api.budgetCategories
      .list(false) // active only
      .then((cats) => setCategories(cats))
      .catch(() => setCategories([]))
      .finally(() => setLoadingCategories(false));

    if (item) {
      reset({
        category_id: item.category_id,
        description: item.description,
        planned_amount: parseFloat(item.planned_amount),
        notes: item.notes ?? "",
      });
    } else {
      reset({
        category_id: 0,
        description: "",
        planned_amount: 0,
        notes: "",
      });
    }
  }, [open, item, reset]);

  async function onSubmit(data: BudgetItemFormInput) {
    const payload = {
      category_id: data.category_id,
      description: data.description,
      planned_amount: data.planned_amount,
      notes: data.notes || null,
    };

    try {
      if (item) {
        await api.budgetItems.update(item.id, payload);
      } else {
        await api.budgetItems.createForProject(projectId, payload);
      }
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Operation failed";
      alert(message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Budget Item" : "New Budget Item"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the budget line item details below."
              : "Add a planned budget line under one of the categories."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label>Category</Label>
            <Select
              value={categoryValue ? String(categoryValue) : ""}
              onValueChange={(v) => setValue("category_id", parseInt(v, 10))}
              disabled={loadingCategories}
            >
              <SelectTrigger>
                <SelectValue placeholder={loadingCategories ? "Loading..." : "Select category"} />
              </SelectTrigger>
              <SelectContent>
                {categories.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.category_id && (
              <p className="text-xs text-destructive">{errors.category_id.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              placeholder="e.g. Concrete and rebar"
              {...register("description")}
            />
            {errors.description && (
              <p className="text-xs text-destructive">{errors.description.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="planned_amount">Planned Amount (₽)</Label>
            <Input
              id="planned_amount"
              type="number"
              step="0.01"
              min="0"
              {...register("planned_amount", { valueAsNumber: true })}
            />
            {errors.planned_amount && (
              <p className="text-xs text-destructive">{errors.planned_amount.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes (optional)</Label>
            <Textarea
              id="notes"
              placeholder="Vendor, scope, assumptions..."
              rows={3}
              {...register("notes")}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEdit ? "Save changes" : "Add item"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
