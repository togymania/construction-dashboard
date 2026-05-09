"use client";

import { useCallback, useState } from "react";
import {
  Upload,
  FileSpreadsheet,
  X,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  Loader2,
  ArrowLeft,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError } from "@/lib/api-client";
import { formatRubCompact } from "@/lib/formatters";
import { useT } from "@/lib/i18n/provider";
import type {
  AcceptedMatch,
  ImportPreview,
  ImportResult,
} from "@/types/ledger";

type Step = "upload" | "preview" | "result";

type CompanyDecision = "accept" | "skip";

interface Props {
  onClose: () => void;
  onComplete: () => void;
}

export function LedgerImportWizard({ onClose, onComplete }: Props) {
  const { t } = useT();
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [decisions, setDecisions] = useState<Record<string, CompanyDecision>>(
    {}
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // ---------- Step 1: Upload ----------

  const handleFile = useCallback((f: File) => {
    if (!f.name.toLowerCase().endsWith(".xlsx")) {
      setError(t("expenses.import.errInvalidFile"));
      return;
    }
    setFile(f);
    setError(null);
  }, [t]);

  async function uploadFile() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api.ledger.importPreview(file);
      setPreview(p);

      // Pre-set decisions: accept = high_confidence, skip = others
      const initial: Record<string, CompanyDecision> = {};
      for (const m of p.match_proposals) {
        if (m.candidate_id !== null) {
          initial[m.company_name] = m.high_confidence ? "accept" : "skip";
        }
      }
      setDecisions(initial);

      setStep("preview");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : t("expenses.import.errParse"),
      );
    } finally {
      setBusy(false);
    }
  }

  // ---------- Step 2: Preview + match review ----------

  function setDecision(company: string, d: CompanyDecision) {
    setDecisions((cur) => ({ ...cur, [company]: d }));
  }

  function bulkAcceptHighConfidence() {
    if (!preview) return;
    const next: Record<string, CompanyDecision> = { ...decisions };
    for (const m of preview.match_proposals) {
      if (m.candidate_id !== null && m.high_confidence) {
        next[m.company_name] = "accept";
      }
    }
    setDecisions(next);
  }

  function bulkAcceptAllProposed() {
    if (!preview) return;
    const next: Record<string, CompanyDecision> = { ...decisions };
    for (const m of preview.match_proposals) {
      if (m.candidate_id !== null) {
        next[m.company_name] = "accept";
      }
    }
    setDecisions(next);
  }

  function bulkSkipAll() {
    if (!preview) return;
    const next: Record<string, CompanyDecision> = { ...decisions };
    for (const m of preview.match_proposals) {
      if (m.candidate_id !== null) {
        next[m.company_name] = "skip";
      }
    }
    setDecisions(next);
  }

  async function commit() {
    if (!preview) return;
    setBusy(true);
    setError(null);

    // Build accepted_matches from decisions
    const accepted: AcceptedMatch[] = [];
    for (const m of preview.match_proposals) {
      if (m.candidate_id === null) continue;
      const d = decisions[m.company_name];
      if (d === "accept") {
        accepted.push({
          company_name: m.company_name,
          subcontractor_id: m.candidate_id,
        });
      }
    }

    try {
      const r = await api.ledger.importCommit({
        import_token: preview.import_token,
        accepted_matches: accepted,
      });
      setResult(r);
      setStep("result");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : t("expenses.import.errCommit"),
      );
    } finally {
      setBusy(false);
    }
  }

  function finishAndRefresh() {
    onComplete();
  }

  // ---------- Render ----------

  const matchedProposals = preview?.match_proposals.filter((p) => p.candidate_id !== null) ?? [];
  const acceptCount = Object.values(decisions).filter((d) => d === "accept").length;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-primary" />
            {step === "upload" && t("expenses.import.titleUpload")}
            {step === "preview" && t("expenses.import.titlePreview")}
            {step === "result" && t("expenses.import.titleResult")}
          </DialogTitle>
          <DialogDescription>
            {step === "upload" &&
              t("expenses.import.descUpload")}
            {step === "preview" &&
              t("expenses.import.descPreview")}
            {step === "result" &&
              t("expenses.import.descResult")}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="flex items-start gap-2 rounded-md bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-400">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* ---- Step 1: Upload ---- */}
        {step === "upload" && (
          <div className="space-y-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const f = e.dataTransfer.files[0];
                if (f) handleFile(f);
              }}
              className={`flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-12 transition-colors ${
                dragOver
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/25 hover:border-primary/50"
              }`}
            >
              <Upload className="h-10 w-10 text-muted-foreground" />
              <div className="text-center">
                <p className="text-sm font-medium">
                  {t("expenses.import.dropHere")}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("expenses.import.orClick")}
                </p>
              </div>
              <label className="cursor-pointer">
                <Button variant="outline" type="button" asChild>
                  <span>{t("expenses.import.chooseFile")}</span>
                </Button>
                <input
                  type="file"
                  accept=".xlsx"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFile(f);
                  }}
                />
              </label>
            </div>

            {file && (
              <Card>
                <CardContent className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <FileSpreadsheet className="h-5 w-5 text-primary" />
                    <div>
                      <p className="text-sm font-medium">{file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {(file.size / 1024 / 1024).toFixed(1)} MB
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setFile(null)}
                    disabled={busy}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose} disabled={busy}>
                {t("common.cancel")}
              </Button>
              <Button onClick={uploadFile} disabled={!file || busy} className="gap-2">
                {busy ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                {t("expenses.import.parseFile")}
              </Button>
            </div>
          </div>
        )}

        {/* ---- Step 2: Preview ---- */}
        {step === "preview" && preview && (
          <div className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SummaryStat
                label={t("expenses.import.parsed")}
                value={preview.total_rows_parsed.toString()}
              />
              <SummaryStat
                label={t("expenses.import.toImport")}
                value={preview.rows_to_import.toString()}
                accent="text-emerald-600 dark:text-emerald-400"
              />
              <SummaryStat
                label={t("expenses.import.dupsInDb")}
                value={preview.duplicates_in_db.toString()}
                accent={preview.duplicates_in_db > 0 ? "text-amber-600 dark:text-amber-400" : ""}
              />
              <SummaryStat
                label={t("expenses.import.dupsInFile")}
                value={preview.duplicates_in_file.toString()}
                accent={preview.duplicates_in_file > 0 ? "text-amber-600 dark:text-amber-400" : ""}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <SummaryStat
                label={t("expenses.import.income")}
                value={`${preview.income_count} (${formatRubCompact(preview.income_total)})`}
                accent="text-emerald-600 dark:text-emerald-400"
              />
              <SummaryStat
                label={t("expenses.import.expense")}
                value={`${preview.expense_count} (${formatRubCompact(preview.expense_total)})`}
                accent="text-rose-600 dark:text-rose-400"
              />
            </div>

            {preview.parse_errors.length > 0 && (
              <div className="rounded-md bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400">
                <p className="font-medium">
                  {preview.parse_errors.length}{" "}
                  {t("expenses.import.parseErrors")}
                </p>
                <ul className="mt-1 list-inside list-disc space-y-0.5">
                  {preview.parse_errors.slice(0, 5).map((e, i) => (
                    <li key={i}>
                      Satır {e.source_row}: {e.reason}
                    </li>
                  ))}
                  {preview.parse_errors.length > 5 && (
                    <li>
                      …{preview.parse_errors.length - 5}{" "}
                      {t("expenses.import.moreErrors")}
                    </li>
                  )}
                </ul>
              </div>
            )}

            {/* Match proposals */}
            <div className="rounded-md border">
              <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2">
                <p className="text-sm font-medium">
                  {t("expenses.import.matchTitle")} (
                  {matchedProposals.length})
                </p>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={bulkAcceptHighConfidence}>
                    {t("expenses.import.acceptHigh")}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={bulkAcceptAllProposed}>
                    {t("expenses.import.acceptAll")}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={bulkSkipAll}>
                    {t("expenses.import.skipAll")}
                  </Button>
                </div>
              </div>

              {matchedProposals.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                  {t("expenses.import.noMatches")}
                  <p className="mt-2 text-xs">
                    {t("expenses.import.noMatchesHint")}
                  </p>
                </div>
              ) : (
                <div className="max-h-[300px] overflow-y-auto">
                  <Table>
                    <TableHeader className="sticky top-0 bg-background">
                      <TableRow>
                        <TableHead>
                          {t("expenses.import.companyCol")}
                        </TableHead>
                        <TableHead className="w-[60px]">
                          {t("expenses.import.occCol")}
                        </TableHead>
                        <TableHead>
                          {t("expenses.import.proposedCol")}
                        </TableHead>
                        <TableHead className="w-[80px]">
                          {t("expenses.import.scoreCol")}
                        </TableHead>
                        <TableHead className="w-[160px] text-right">
                          {t("expenses.import.decisionCol")}
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {matchedProposals.map((p) => {
                        const d = decisions[p.company_name] ?? "skip";
                        return (
                          <TableRow key={p.company_name}>
                            <TableCell className="text-xs">
                              <span className="line-clamp-1">{p.company_name}</span>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {p.occurrences}
                            </TableCell>
                            <TableCell className="text-xs">
                              <span className="line-clamp-1">{p.candidate_name}</span>
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant="secondary"
                                className={
                                  p.high_confidence
                                    ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
                                    : "bg-amber-500/15 text-amber-700 dark:text-amber-400"
                                }
                              >
                                {p.score.toFixed(0)}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="inline-flex rounded-md border">
                                <button
                                  type="button"
                                  onClick={() => setDecision(p.company_name, "accept")}
                                  className={`px-2 py-1 text-xs ${
                                    d === "accept"
                                      ? "bg-emerald-500 text-white"
                                      : "text-muted-foreground hover:bg-muted"
                                  }`}
                                >
                                  {t("expenses.import.accept")}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setDecision(p.company_name, "skip")}
                                  className={`px-2 py-1 text-xs ${
                                    d === "skip"
                                      ? "bg-muted-foreground text-background"
                                      : "text-muted-foreground hover:bg-muted"
                                  }`}
                                >
                                  {t("expenses.import.skip")}
                                </button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}

              {preview.unmatched_companies_count > 0 && (
                <div className="border-t bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
                  +{preview.unmatched_companies_count}{" "}
                  {t("expenses.import.unmatchedNote")}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between gap-2">
              <Button variant="ghost" onClick={() => setStep("upload")} disabled={busy}>
                <ArrowLeft className="mr-1 h-4 w-4" />
                {t("common.back")}
              </Button>
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted-foreground">
                  {acceptCount}{" "}
                  {t("expenses.import.acceptCount")}
                </span>
                <Button onClick={commit} disabled={busy} className="gap-2">
                  {busy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  {t("expenses.import.confirmImport")}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ---- Step 3: Result ---- */}
        {step === "result" && result && (
          <div className="space-y-4">
            <div className="rounded-lg border bg-emerald-500/5 p-6 text-center">
              <CheckCircle2 className="mx-auto mb-3 h-12 w-12 text-emerald-600 dark:text-emerald-400" />
              <h3 className="text-lg font-semibold">
                {t("expenses.import.successTitle")}
              </h3>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <SummaryStat
                label={t("expenses.import.created")}
                value={result.created_count.toString()}
                accent="text-emerald-600 dark:text-emerald-400"
              />
              <SummaryStat
                label={t("expenses.import.skipped")}
                value={result.skipped_duplicate_count.toString()}
              />
              <SummaryStat
                label={t("expenses.import.linked")}
                value={result.linked_to_subcontractor_count.toString()}
                accent="text-blue-600 dark:text-blue-400"
              />
            </div>

            {result.errors.length > 0 && (
              <div className="rounded-md bg-rose-500/10 p-3 text-xs text-rose-700 dark:text-rose-400">
                <p className="font-medium">
                  {result.errors.length} {t("expenses.import.dbErrors")}
                </p>
                <ul className="mt-1 list-inside list-disc space-y-0.5">
                  {result.errors.slice(0, 5).map((e, i) => (
                    <li key={i}>
                      Satır {e.source_row}: {e.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-end">
              <Button onClick={finishAndRefresh}>
                {t("expenses.import.done")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function SummaryStat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-base font-semibold ${accent ?? ""}`}>{value}</p>
    </div>
  );
}
