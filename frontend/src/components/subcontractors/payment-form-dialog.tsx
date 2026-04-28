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
import { AlertCircle } from "lucide-react";
import { api } from "@/lib/api-client";
import type {
  PaymentPayload,
  PaymentStatus,
  SubcontractorPayment,
} from "@/types/subcontractor";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subcontractorId: number;
  contractId: number;
  /** null = create, populated = edit */
  payment: SubcontractorPayment | null;
  /** Optional info for over-payment soft-warning preview */
  contractAmount?: number;
  currentPaidPlusPending?: number;
  onSuccess: () => void;
}

export function PaymentFormDialog({
  open,
  onOpenChange,
  subcontractorId,
  contractId,
  payment,
  contractAmount,
  currentPaidPlusPending,
  onSuccess,
}: Props) {
  const isEdit = payment !== null;

  const [paymentNumber, setPaymentNumber] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [paymentDate, setPaymentDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [status, setStatus] = useState<PaymentStatus>("pending");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [notes, setNotes] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (payment) {
      setPaymentNumber(String(payment.payment_number));
      setDescription(payment.description);
      setAmount(payment.amount);
      setPaymentDate(payment.payment_date);
      setDueDate(payment.due_date ?? "");
      setStatus(payment.status);
      setInvoiceNumber(payment.invoice_number ?? "");
      setNotes(payment.notes ?? "");
    } else {
      setPaymentNumber(""); // backend will auto-assign
      setDescription("");
      setAmount("");
      setPaymentDate(new Date().toISOString().slice(0, 10));
      setDueDate("");
      setStatus("pending");
      setInvoiceNumber("");
      setNotes("");
    }
    setError(null);
  }, [open, payment]);

  // Live over-payment preview (soft, advisory only)
  const parsedAmount = parseFloat(amount);
  let overPayWarning: string | null = null;
  if (
    !isNaN(parsedAmount) &&
    parsedAmount > 0 &&
    contractAmount !== undefined &&
    currentPaidPlusPending !== undefined
  ) {
    const baseline = isEdit
      ? currentPaidPlusPending - parseFloat(payment!.amount)
      : currentPaidPlusPending;
    const projected = baseline + parsedAmount;
    if (projected > contractAmount) {
      overPayWarning = `This will exceed contract amount by ${(
        projected - contractAmount
      ).toLocaleString("en-US", { maximumFractionDigits: 2 })} ₽. The backend will accept it but flag a warning.`;
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!description.trim()) {
      setError("Description is required");
      return;
    }
    if (!paymentDate) {
      setError("Payment date is required");
      return;
    }
    const amt = parseFloat(amount);
    if (isNaN(amt) || amt <= 0) {
      setError("Amount must be a positive number");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (isEdit && payment) {
        // PATCH update payload (no payment_number changes)
        await api.subcontractors.payments.update(
          subcontractorId,
          contractId,
          payment.id,
          {
            description: description.trim(),
            amount: amt,
            payment_date: paymentDate,
            due_date: dueDate || null,
            status,
            invoice_number: invoiceNumber.trim() || null,
            notes: notes.trim() || null,
          }
        );
      } else {
        // Create: payment_number optional (null -> backend auto-assigns)
        const payload: PaymentPayload = {
          payment_number: paymentNumber.trim()
            ? parseInt(paymentNumber, 10)
            : null,
          description: description.trim(),
          amount: amt,
          payment_date: paymentDate,
          due_date: dueDate || null,
          status,
          invoice_number: invoiceNumber.trim() || null,
          notes: notes.trim() || null,
        };
        await api.subcontractors.payments.create(
          subcontractorId,
          contractId,
          payload
        );
      }
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? `Edit Payment #${payment!.payment_number}` : "Add Payment"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Payment number + status row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="pf-num">
                Payment #{" "}
                <span className="text-muted-foreground text-xs">
                  {isEdit ? "(read-only)" : "(blank = auto)"}
                </span>
              </Label>
              <Input
                id="pf-num"
                type="number"
                min="1"
                value={paymentNumber}
                onChange={(e) => setPaymentNumber(e.target.value)}
                placeholder="auto"
                disabled={isEdit}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pf-status">Status</Label>
              <Select
                value={status}
                onValueChange={(v) => setStatus(v as PaymentStatus)}
              >
                <SelectTrigger id="pf-status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="paid">Paid</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="pf-desc">
              Description <span className="text-destructive">*</span>
            </Label>
            <Input
              id="pf-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              placeholder="Q3 2024 progress payment"
            />
          </div>

          {/* Amount */}
          <div className="space-y-2">
            <Label htmlFor="pf-amount">
              Amount (₽) <span className="text-destructive">*</span>
            </Label>
            <Input
              id="pf-amount"
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="200000000"
            />
            {overPayWarning && (
              <p className="text-xs text-amber-600 dark:text-amber-400 flex items-start gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                <span>{overPayWarning}</span>
              </p>
            )}
          </div>

          {/* Dates row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="pf-date">
                Payment Date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="pf-date"
                type="date"
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pf-due">
                Due Date{" "}
                <span className="text-muted-foreground text-xs">(optional)</span>
              </Label>
              <Input
                id="pf-due"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>
          </div>

          {/* Invoice */}
          <div className="space-y-2">
            <Label htmlFor="pf-invoice">
              Invoice #{" "}
              <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Input
              id="pf-invoice"
              value={invoiceNumber}
              onChange={(e) => setInvoiceNumber(e.target.value)}
              maxLength={100}
              placeholder="FT-2024-0987"
            />
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="pf-notes">
              Notes{" "}
              <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Textarea
              id="pf-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

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
              {saving ? "Saving..." : isEdit ? "Update" : "Add"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
