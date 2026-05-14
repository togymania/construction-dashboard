"use client";

import { useEffect, useMemo, useState } from "react";
import { Wallet, Link2, Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, ApiError } from "@/lib/api-client";
import { useT } from "@/lib/i18n/provider";
import { formatRub, formatRubCompact } from "@/lib/formatters";
import type { SubcontractorPaymentEntry } from "@/types/ledger";
import type { SubcontractorContract } from "@/types/subcontractor";

interface Props {
  subcontractorId: number;
  contracts: SubcontractorContract[] | null;
  canEdit: boolean;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function LedgerPaymentsTab({
  subcontractorId,
  contracts,
  canEdit,
}: Props) {
  const { t } = useT();
  const [entries, setEntries] = useState<SubcontractorPaymentEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);

  async function load() {
    setError(null);
    try {
      const data = await api.ledger.bySubcontractor(subcontractorId);
      setEntries(data);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : t("expenses.import.errParse"),
      );
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subcontractorId]);

  async function assignContract(entryId: number, contractId: number | null) {
    setSavingId(entryId);
    try {
      await api.ledger.update(entryId, { contract_id: contractId });
      // Update local state
      setEntries((cur) =>
        cur
          ? cur.map((e) =>
              e.id === entryId
                ? {
                    ...e,
                    contract_id: contractId,
                    contract_number:
                      contracts?.find((c) => c.id === contractId)?.contract_number ?? null,
                  }
                : e,
            )
          : cur,
      );
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Kontrat atama hatası",
      );
    } finally {
      setSavingId(null);
    }
  }

  const totals = useMemo(() => {
    if (!entries) return null;
    let income = 0;
    let expense = 0;
    let unassignedToContract = 0;
    for (const e of entries) {
      const amt = parseFloat(e.amount);
      if (e.entry_type === "income") income += amt;
      else expense += amt;
      if (e.contract_id === null) unassignedToContract += 1;
    }
    return { income, expense, unassignedToContract, count: entries.length };
  }, [entries]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          {t("expenses.payments")}
        </h2>
        {totals && (
          <div className="flex gap-3 text-xs text-muted-foreground">
            <span>
              {totals.count} {t("expenses.kpi.entries")}
            </span>
            <span className="text-emerald-600 dark:text-emerald-400">
              +{formatRubCompact(totals.income)}
            </span>
            <span className="text-rose-600 dark:text-rose-400">
              −{formatRubCompact(totals.expense)}
            </span>
            {totals.unassignedToContract > 0 && (
              <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-amber-700 dark:text-amber-400">
                {totals.unassignedToContract}{" "}
                {t("expenses.paymentsUnassigned")}
              </span>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-400">
          {error}
        </div>
      )}

      <Card>
        <CardContent className="pt-6">
          {entries === null ? (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <Wallet className="mb-3 h-8 w-8 opacity-40" />
              <p className="text-sm">
                {t("expenses.payments")}
              </p>
              <p className="mt-1 text-xs">
                Excel içe aktarmasında bu taşeron için eşleşme onaylanırsa burada
                görünür.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table className="w-full table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[88px]">
                      {t("expenses.col.date")}
                    </TableHead>
                    <TableHead className="w-[88px]">
                      {t("expenses.col.kod")}
                    </TableHead>
                    <TableHead>
                      {t("expenses.col.description")}
                    </TableHead>
                    <TableHead className="w-[110px] text-right">
                      {t("expenses.col.amount")}
                    </TableHead>
                    <TableHead className="w-[140px]">
                      {t("expenses.col.contract")}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.map((e) => (
                    <TableRow key={e.id}>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDate(e.entry_date)}
                      </TableCell>
                      <TableCell>
                        {e.kod ? (
                          <Badge variant="secondary" className="font-mono text-[10px]">
                            {e.kod}
                          </Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        <span
                          className="block truncate"
                          title={e.description || undefined}
                        >
                          {e.description || "—"}
                        </span>
                      </TableCell>
                      <TableCell
                        className={`text-right font-mono text-sm font-medium ${
                          e.entry_type === "income"
                            ? "text-emerald-600 dark:text-emerald-400"
                            : "text-rose-600 dark:text-rose-400"
                        }`}
                      >
                        {e.entry_type === "income" ? "+" : "−"}
                        {formatRub(e.amount).replace(" ₽", "")}
                      </TableCell>
                      <TableCell>
                        {!canEdit ? (
                          e.contract_number ? (
                            <Badge variant="outline" className="text-xs">
                              <Link2 className="mr-1 h-3 w-3" />
                              {e.contract_number}
                            </Badge>
                          ) : (
                            <span className="text-xs italic text-muted-foreground">
                              atanmamış
                            </span>
                          )
                        ) : savingId === e.id ? (
                          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        ) : (
                          <Select
                            value={e.contract_id ? String(e.contract_id) : "none"}
                            onValueChange={(v) =>
                              assignContract(e.id, v === "none" ? null : parseInt(v))
                            }
                          >
                            <SelectTrigger className="h-8 text-xs">
                              <SelectValue placeholder="Kontrat seç..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">
                                <span className="italic text-muted-foreground">
                                  atanmamış
                                </span>
                              </SelectItem>
                              {(contracts ?? []).map((c) => (
                                <SelectItem key={c.id} value={String(c.id)}>
                                  {c.contract_number ?? `#${c.id}`} —{" "}
                                  {c.description?.slice(0, 30)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
