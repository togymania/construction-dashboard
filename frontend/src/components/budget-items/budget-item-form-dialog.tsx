"use client";

import { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
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

import { api } from "@/lib/api-client";
import {
  budgetItemFormSchema,
  type BudgetItemFormInput,
  type BudgetItemFormOutput,
} from "@/lib/validators/budget-item-schema";
import type { BudgetCategory, BudgetItem } from "@/types/budget";
import {
  CategoryCombobox,
  comboboxValueToPayload,
  comboboxValueFromExisting,
  type CategoryComboboxValue,
} from "@/components/category-combobox";

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

  // Combobox state lives outside the form because the value shape
  // (CategoryComboboxValue) is richer than what zod ultimately stores.
  // We sync it into the form via Controller below.
  const [categoryValue, setCategoryValue] = useState<CategoryComboboxValue>(null);

  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<BudgetItemFormInput>({
    resolver: zodResolver(budgetItemFormSchema),
    defaultValues: {
      category_id: null,
      category_name_new: null,
      description: "",
      planned_amount: 0,
      notes: "",
    },
  });

  // Load categories whenever the dialog opens.
  useEffect(() => {
    if (!open) return;

    setLoadingCategories(true);
    api.budgetCategories
      .list(false) // active only
      .then((cats) => setCategories(cats))
      .catch(() => setCategories([]))
      .finally(() => setLoadingCategories(false));

    if (item) {
      const initialValue = comboboxValueFromExisting({
        id: item.category_id,
        name: item.category.name,
      });
      setCategoryValue(initialValue);
      reset({
        category_id: item.category_id,
        category_name_new: null,
        description: item.description,
        planned_amount: parseFloat(item.planned_amount),
        notes: item.notes ?? "",
      });
    } else {
      setCategoryValue(null);
      reset({
        category_id: null,
        category_name_new: null,
        description: "",
        planned_amount: 0,
        notes: "",
      });
    }
  }, [open, item, reset]);

  // Whenever the user picks something in the combobox, mirror it into form state
  // so zod validation sees the latest values.
  useEffect(() => {
    const cat = comboboxValueToPayload(categoryValue);
    setValue("category_id", cat.category_id, { shouldValidate: true });
    setValue("category_name_new", cat.category_name_new, { shouldValidate: true });
  }, [categoryValue, setValue]);

  async function onSubmit(rawData: BudgetItemFormInput) {
    // After zod transform, numeric fields are real numbers.
    const data = rawData as unknown as BudgetItemFormOutput;

    const payload = {
      category_id: data.category_id ?? null,
      category_name_new: data.category_name_new ?? null,
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
              : "Add a planned budget line under a category. You can pick an existing category or type a new one."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Category combobox (managed via separate state, mirrored into form) */}
          <div className="space-y-2">
            <Label>Category</Label>
            <Controller
              control={control}
              name="category_id"
              render={() => (
                <CategoryCombobox
                  categories={categories}
                  value={categoryValue}
                  onChange={setCategoryValue}
                  disabled={loadingCategories}
                  placeholder={
                    loadingCategories
                      ? "Loading categories..."
                      : "Select or create category..."
                  }
                />
              )}
            />
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
              {...register("planned_amount")}
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
