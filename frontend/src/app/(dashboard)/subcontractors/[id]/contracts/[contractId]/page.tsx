"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  FileText,
  Wallet,
  CheckCircle2,
  Clock,
  AlertCircle,
  Plus,
  Calendar,
  Building2,
  MoreHorizontal,
  Pencil,
  Trash2,
  CheckCheck,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
  StatusBadge,
  CONTRACT_STATUS_COLORS,
  PAYMENT_STATUS_COLORS,
} from "@/components/ui/status-badge";

import { api } from "@/lib/api-client";
import { formatRub, formatRubCompact, formatDate } from "@/lib/formatters";
import { useUser } from "@/components/providers/user-provider";
import { PaymentFormDialog } from "@/components/subcontractors/payment-form-dialog";
import type {
  SubcontractorContract,
  SubcontractorPayment,
} from "@/types/subcontractor";

export default function ContractDetailPage() {
  const params = useParams<{ id: string; contractId: string }>();
  const subId = parseInt(params.id, 10);
  const contractId = parseInt(params.contractId, 10);

  const { user } = useUser();
  const canEdit =
    user && (user.role === "admin" || user.role === "project_manager");

  const [contract, setContract] = useState<SubcontractorContract | null>(null);
  const [payments, setPayments] = useState<SubcontractorPayment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadAll() {
    if (Number.isNaN(subId) || Number.isNaN(contractId)) return;
    setError(null);
    try {
      const [c, p] = await Promise.all([
        api.subcontractors.contracts.get(subId, contractId),
        api.subcontractors.payments.list(subId, contractId),
      ]);
      setContract(c);
      setPayments(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subId, contractId]);

  // Payment form dialog state
  const [payFormOpen, setPayFormOpen] = useState(false);
  const [editingPayment, setEditingPayment] = useState<SubcontractorPayment | null>(null);

  function openCreatePayment() {
    setEditingPayment(null);
    setPayFormOpen(true);
  }

  function openEditPayment(p: SubcontractorPayment) {
    setEditingPayment(p);
    setPayFormOpen(true);
  }

  async function handleApprovePayment(p: SubcontractorPayment) {
    try {
      await api.subcontractors.payments.update(subId, contractId, p.id, {
        status: "approved",
      });
      await loadAll();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function handleDeletePayment(p: SubcontractorPayment) {
    if (
      !confirm(
        `Delete payment #${p.payment_number} (${p.description})? ` +
          "PAID payments cannot be deleted; the API will reject them."
      )
    )
      return;
    try {
      await api.subcontractors.payments.delete(subId, contractId, p.id);
      await loadAll();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  }

  if (Number.isNaN(subId) || Number.isNaN(contractId)) {
    return <div className="p-6 text-destructive">Invalid IDs</div>;
  }

  if (contract === null) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const contractAmt = parseFloat(contract.contract_amount);
  const paidAmt = parseFloat(contract.paid_amount);
  const pendingAmt = parseFloat(contract.pending_amount);
  const remaining = contractAmt - paidAmt;
  const paidPct = contractAmt > 0 ? (paidAmt / contractAmt) * 100 : 0;
  const overPaid = paidAmt + pendingAmt > contractAmt;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href={`/subcontractors/${subId}`}
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to subcontractor
      </Link>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Contract info card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="space-y-3 flex-1">
              <div className="flex items-center gap-3 flex-wrap">
                <FileText className="h-6 w-6 text-muted-foreground" />
                <h1 className="text-xl font-bold tracking-tight">
                  {contract.contract_number ?? `Contract #${contract.id}`}
                </h1>
                <StatusBadge
                  status={contract.status}
                  colorMap={CONTRACT_STATUS_COLORS}
                />
                {contract.is_overdue && (
                  <span className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400 font-medium border border-red-300 dark:border-red-900 px-2 py-0.5 rounded-md">
                    <AlertCircle className="h-3 w-3" />
                    Overdue
                  </span>
                )}
              </div>

              <p className="text-sm">{contract.description}</p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm pt-2">
                {contract.subcontractor && (
                  <div className="flex items-start gap-1.5">
                    <Building2 className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                    <div>
                      <span className="text-muted-foreground block">
                        Subcontractor
                      </span>
                      <Link
                        href={`/subcontractors/${contract.subcontractor.id}`}
                        className="font-medium hover:underline"
                      >
                        {contract.subcontractor.name}
                      </Link>
                    </div>
                  </div>
                )}
                {contract.project && (
                  <div className="flex items-start gap-1.5">
                    <Building2 className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                    <div>
                      <span className="text-muted-foreground block">Project</span>
                      <span className="font-medium">{contract.project.name}</span>
                    </div>
                  </div>
                )}
                <div className="flex items-start gap-1.5">
                  <Calendar className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                  <div>
                    <span className="text-muted-foreground block">Period</span>
                    <span className="font-medium">
                      {formatDate(contract.start_date)} → {formatDate(contract.end_date)}
                    </span>
                  </div>
                </div>
              </div>

              {contract.scope_of_work && (
                <div className="text-sm pt-3 border-t">
                  <p className="text-muted-foreground text-xs uppercase tracking-wider mb-1">
                    Scope of work
                  </p>
                  <p>{contract.scope_of_work}</p>
                </div>
              )}
              {contract.notes && (
                <div className="text-sm pt-2">
                  <p className="text-muted-foreground text-xs uppercase tracking-wider mb-1">
                    Notes
                  </p>
                  <p>{contract.notes}</p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Progress bar + financial summary */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              Payment progress
            </span>
            <span className="font-medium">
              {formatRubCompact(paidAmt)} / {formatRubCompact(contractAmt)} ({paidPct.toFixed(1)}%)
            </span>
          </div>
          <div className="h-3 w-full bg-muted rounded-full overflow-hidden">
            <div
              className={
                "h-full transition-all " +
                (overPaid
                  ? "bg-red-500 dark:bg-red-600"
                  : paidPct >= 100
                  ? "bg-emerald-500 dark:bg-emerald-600"
                  : "bg-blue-500 dark:bg-blue-600")
              }
              style={{ width: `${Math.min(100, paidPct)}%` }}
            />
          </div>

          {overPaid && (
            <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5" />
              Total payments (paid + pending) exceed contract amount.
            </p>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 text-sm">
            <div>
              <p className="text-muted-foreground text-xs">Contract amount</p>
              <p className="font-semibold">{formatRub(contractAmt)}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">Paid</p>
              <p className="font-semibold text-emerald-600 dark:text-emerald-400">
                {formatRub(paidAmt)}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">Pending / Approved</p>
              <p className="font-semibold text-amber-600 dark:text-amber-400">
                {formatRub(pendingAmt)}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">Remaining</p>
              <p className={"font-semibold " + (remaining < 0 ? "text-red-600 dark:text-red-400" : "")}>
                {formatRub(remaining)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Payments table */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          Payments {payments ? `(${payments.length})` : ""}
        </h2>
        {canEdit && (
          <Button onClick={openCreatePayment}>
            <Plus className="h-4 w-4 mr-2" />
            Add Payment
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="pt-6">
          {payments === null ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : payments.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Wallet className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p>No payments recorded for this contract yet.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Payment Date</TableHead>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  {canEdit && <TableHead className="w-12"></TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {payments.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-mono text-xs">{p.payment_number}</TableCell>
                    <TableCell className="max-w-xs">
                      <div className="truncate" title={p.description}>
                        {p.description}
                      </div>
                      {p.over_payment_warning && (
                        <p className="text-[10px] text-amber-600 dark:text-amber-400 mt-0.5 flex items-center gap-1">
                          <AlertCircle className="h-2.5 w-2.5" />
                          {p.over_payment_warning}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="text-xs whitespace-nowrap">
                      <div>{formatDate(p.payment_date)}</div>
                      {p.due_date && (
                        <div className="text-muted-foreground">
                          due {formatDate(p.due_date)}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {p.invoice_number ?? "-"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        status={p.status}
                        colorMap={PAYMENT_STATUS_COLORS}
                      />
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatRub(p.amount)}
                    </TableCell>
                    {canEdit && (
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => openEditPayment(p)}>
                              <Pencil className="h-4 w-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            {p.status === "pending" && (
                              <DropdownMenuItem onClick={() => handleApprovePayment(p)}>
                                <CheckCheck className="h-4 w-4 mr-2" />
                                Mark as Approved
                              </DropdownMenuItem>
                            )}
                            {p.status !== "paid" && (
                              <DropdownMenuItem
                                onClick={() => handleDeletePayment(p)}
                                className="text-destructive focus:text-destructive"
                              >
                                <Trash2 className="h-4 w-4 mr-2" />
                                Delete
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Add / Edit payment dialog */}
      <PaymentFormDialog
        open={payFormOpen}
        onOpenChange={setPayFormOpen}
        subcontractorId={subId}
        contractId={contractId}
        payment={editingPayment}
        contractAmount={parseFloat(contract.contract_amount)}
        currentPaidPlusPending={paidAmt + pendingAmt}
        onSuccess={loadAll}
      />

      {/* Soft summary at bottom */}
      <div className="text-xs text-muted-foreground flex items-center gap-3">
        <span className="flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3 text-emerald-500" />
          Paid
        </span>
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3 text-amber-500" />
          Pending / Approved
        </span>
      </div>
    </div>
  );
}
