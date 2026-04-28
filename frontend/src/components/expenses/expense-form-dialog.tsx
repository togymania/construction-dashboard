"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
  CategoryCombobox,
  comboboxValueToPayload,
  comboboxValueFromExisting,
  type CategoryComboboxValue,
} from "@/components/category-combobox";
import type {
  BudgetCategory,
  BudgetItem,
  Expense,
  ExpensePayload,
} from "@/types/budget";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: number;
  expense: Expense | null; // null → create, populated → edit
  categories: BudgetCategory[];
  budgetItems: BudgetItem[];
  onSuccess: () => void;
}

export function ExpenseFormDialog({
  open,
  onOpenChange,
  projectId,
  expense,
  categories,
  budgetItems,
  onSuccess,
}: Props) {
  const isEdit = expense !== null;

  const [categoryValue, setCategoryValue] = useState<CategoryComboboxValue>(null);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [expenseDate, setExpenseDate] = useState("");
  const [vendor, setVendor] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [budgetItemId, setBudgetItemId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (expense) {
      setCategoryValue(comboboxValueFromExisting({
        id: expense.category_id,
        name: expense.category.name,
      }));
      setDescription(expense.description);
      setAmount(expense.amount);
      setExpenseDate(expense.expense_date);
      setVendor(expense.vendor ?? "");
      setInvoiceNumber(expense.invoice_number ?? "");
      setNotes(expense.notes ?? "");
      setBudgetItemId(
        expense.budget_item_id ? String(expense.budget_item_id) : ""
      );
    } else {
      setCategoryValue(null);
      setDescription("");
      setAmount("");
      setExpenseDate(new Date().toISOString().slice(0, 10));
      setVendor("");
      setInvoiceNumber("");
      setNotes("");
      setBudgetItemId("");
    }
    setError(null);
  }, [open, expense, categories]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!categoryValue || !description.trim() || !amount || !expenseDate) {
      setError("Please fill in all required fields");
      return;
    }
    const parsedAmount = parseFloat(amount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError("Amount must be a positive number");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const cat = comboboxValueToPayload(categoryValue);
      const payload: ExpensePayload = {
        category_id: cat.category_id,
        category_name_new: cat.category_name_new,
        description: description.trim(),
        amount: parsedAmount,
        expense_date: expenseDate,
        vendor: vendor.trim() || null,
        invoice_number: invoiceNumber.trim() || null,
        notes: notes.trim() || null,
        budget_item_id: budgetItemId ? parseInt(budgetItemId, 10) : null,
      };

      if (isEdit && expense) {
        await api.expenses.update(projectId, expense.id, payload);
      } else {
        await api.expenses.createForProject(projectId, payload);
      }
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const activeCategories = categories.filter((c) => c.is_active);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit Expense" : "Add Expense"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Category */}
          <div className="space-y-2">
            <Label htmlFor="exp-category">
              Category <span className="text-destructive">*</span>
            </Label>
            <CategoryCombobox
              categories={categories}
              value={categoryValue}
              onChange={setCategoryValue}
              placeholder="Select or create category..."
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="exp-description">
              Description <span className="text-destructive">*</span>
            </Label>
            <Input
              id="exp-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              placeholder="Concrete delivery for foundation"
            />
          </div>

          {/* Amount + Date row */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="exp-amount">
                Amount (₽) <span className="text-destructive">*</span>
              </Label>
              <Input
                id="exp-amount"
                type="number"
                step="0.01"
                min="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="150000"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="exp-date">
                Payment Date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="exp-date"
                type="date"
                value={expenseDate}
                onChange={(e) => setExpenseDate(e.target.value)}
              />
            </div>
          </div>

          {/* Vendor + Invoice # row */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="exp-vendor">Vendor / Company</Label>
              <Input
                id="exp-vendor"
                value={vendor}
                onChange={(e) => setVendor(e.target.value)}
                maxLength={255}
                placeholder="StroyMontaj LLC"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="exp-invoice">Invoice #</Label>
              <Input
                id="exp-invoice"
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                maxLength={100}
                placeholder="INV-2026-0042"
              />
            </div>
          </div>

          {/* Budget Item (optional) */}
          {budgetItems.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="exp-budget-item">
                Link to Budget Item{" "}
                <span className="text-muted-foreground text-xs">(optional)</span>
              </Label>
              <Select
                value={budgetItemId || "_none"}
                onValueChange={(v) => setBudgetItemId(v === "_none" ? "" : v)}
              >
                <SelectTrigger id="exp-budget-item">
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">None</SelectItem>
                  {budgetItems.map((bi) => (
                    <SelectItem key={bi.id} value={String(bi.id)}>
                      {bi.category.name} — {bi.description}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="exp-notes">
              Notes{" "}
              <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Textarea
              id="exp-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Additional details..."
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : isEdit ? "Update" : "Add Expense"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
