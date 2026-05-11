"use client";

import { useEffect } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { api } from "@/lib/api-client";
import {
  categoryFormSchema,
  type CategoryFormInput,
  type CategoryFormOutput,
} from "@/lib/validators/category-schema";
import type { BudgetCategory } from "@/types/budget";

interface CategoryFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  category?: BudgetCategory | null;
  onSuccess: () => void;
}

function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function CategoryFormDialog({
  open,
  onOpenChange,
  category,
  onSuccess,
}: CategoryFormDialogProps) {
  const isEdit = Boolean(category);
  const isSystem = category?.is_system ?? false;

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CategoryFormInput, unknown, CategoryFormOutput>({
    resolver: zodResolver(categoryFormSchema),
    defaultValues: {
      name: "",
      slug: "",
      display_order: 0,
      is_active: true,
    },
  });

  const isActiveValue = watch("is_active");
  const nameValue = watch("name");
  const slugValue = watch("slug");

  // Auto-generate slug from name (only when creating, not when slug was manually edited)
  useEffect(() => {
    if (isEdit) return;
    if (!nameValue) return;
    const auto = slugify(nameValue);
    // Only update if user hasn't manually typed a different slug
    if (!slugValue || slugify(slugValue) === slugValue) {
      setValue("slug", auto);
    }
  }, [nameValue, slugValue, isEdit, setValue]);

  useEffect(() => {
    if (!open) return;

    if (category) {
      reset({
        name: category.name,
        slug: category.slug,
        display_order: category.display_order,
        is_active: category.is_active,
      });
    } else {
      reset({
        name: "",
        slug: "",
        display_order: 0,
        is_active: true,
      });
    }
  }, [open, category, reset]);

  async function onSubmit(data: CategoryFormOutput) {
    try {
      if (category) {
        // For system categories: backend only accepts display_order + is_active
        const payload = isSystem
          ? {
              display_order: data.display_order,
              is_active: data.is_active,
            }
          : {
              name: data.name,
              slug: data.slug,
              display_order: data.display_order,
              is_active: data.is_active,
            };
        await api.budgetCategories.update(category.id, payload);
      } else {
        await api.budgetCategories.create({
          name: data.name,
          slug: data.slug,
          display_order: data.display_order,
          is_active: data.is_active,
        });
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
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? (isSystem ? "Edit System Category" : "Edit Category") : "New Category"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? isSystem
                ? "System categories have a fixed name and slug. You can only change order and active status."
                : "Update category details below."
              : "Create a new budget category. Slug auto-generates from the name."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              placeholder="e.g. Insurance"
              disabled={isSystem}
              {...register("name")}
            />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            {isSystem && (
              <p className="text-xs text-muted-foreground">
                System category names cannot be changed.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="slug">Slug</Label>
            <Input
              id="slug"
              placeholder="e.g. insurance"
              disabled={isSystem}
              {...register("slug")}
            />
            {errors.slug && <p className="text-xs text-destructive">{errors.slug.message}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="display_order">Display Order</Label>
              <Input
                id="display_order"
                type="number"
                min="0"
                {...register("display_order", { valueAsNumber: true })}
              />
              {errors.display_order && (
                <p className="text-xs text-destructive">{errors.display_order.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Status</Label>
              <Select
                value={isActiveValue ? "true" : "false"}
                onValueChange={(v) => setValue("is_active", v === "true")}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">Active</SelectItem>
                  <SelectItem value="false">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
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
              {isEdit ? "Save changes" : "Create category"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
