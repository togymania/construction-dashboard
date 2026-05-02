"use client";

import { useRef, useState } from "react";
import {
  FileSpreadsheet,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Info,
  X,
  Sparkles,
  Loader2,
  XCircle,
  Building2,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import type {
  WorkforceImportResponse,
  WorkforceMultiImportResponse,
  WorkforceImportWarning,
} from "@/types/workforce";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: number;
  onComplete: () => void;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const MAX_FILES = 10;

function isValidExcel(name: string): boolean {
  return name.toLowerCase().endsWith(".xlsx");
}

export function WorkforceUploadDialog({
  open,
  onOpenChange,
  projectId,
  onComplete,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WorkforceMultiImportResponse | null>(null);

  function reset() {
    setFiles([]);
    setError(null);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    if (selected.length === 0) return;

    // Validate
    const errors: string[] = [];
    const valid: File[] = [];

    for (const f of selected) {
      if (!isValidExcel(f.name)) {
        errors.push(`${f.name}: only .xlsx accepted`);
        continue;
      }
      if (f.size > MAX_FILE_SIZE) {
        errors.push(`${f.name}: exceeds 10 MB`);
        continue;
      }
      valid.push(f);
    }

    if (valid.length + files.length > MAX_FILES) {
      setError(`Too many files (max ${MAX_FILES})`);
      return;
    }

    if (errors.length > 0) {
      setError(errors.join("; "));
    } else {
      setError(null);
    }
    setFiles((prev) => [...prev, ...valid]);
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleImport() {
    if (files.length === 0) return;
    setImporting(true);
    setError(null);
    try {
      const res = await api.workforce.importExcel(projectId, files);
      setResult(res);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Upload failed - check the file format"
      );
    } finally {
      setImporting(false);
    }
  }

  function handleDone() {
    onComplete();
    reset();
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-primary" />
            Upload Daily Puantaj
          </DialogTitle>
        </DialogHeader>

        {/* === Step 1: file picker === */}
        {result === null && (
          <div className="space-y-4 py-2">
            <p className="text-sm text-muted-foreground">
              Pick one or more .xlsx files. Each must be in cover-page format -
              the company is auto-detected from the header (Monotekstroy / Monart).
              Existing snapshots for the same date and company will be replaced.
            </p>

            <div className="border border-dashed border-foreground/15 rounded-xl p-6 bg-card/40 hover:bg-card/60 transition-colors">
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                id="workforce-upload-input"
              />
              <label
                htmlFor="workforce-upload-input"
                className="flex flex-col items-center justify-center gap-2 cursor-pointer"
              >
                <Upload className="h-8 w-8 text-muted-foreground" />
                <span className="text-sm font-medium">
                  {files.length === 0 ? "Click to choose files" : "Add more files"}
                </span>
                <span className="text-xs text-muted-foreground">
                  .xlsx only, up to 10 MB each
                </span>
              </label>
            </div>

            {/* Selected files list */}
            {files.length > 0 && (
              <div className="space-y-1.5">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {files.length} {files.length === 1 ? "file" : "files"} selected
                </div>
                <ul className="space-y-1">
                  {files.map((f, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-3 text-sm bg-card/40 border border-foreground/8 rounded-md px-3 py-2"
                    >
                      <FileSpreadsheet className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="flex-1 truncate">{f.name}</span>
                      <span className="text-xs text-muted-foreground tabular-nums shrink-0">
                        {(f.size / 1024).toFixed(1)} KB
                      </span>
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-destructive transition-colors"
                        onClick={() => removeFile(i)}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md p-3">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>
        )}

        {/* === Step 2: result panel === */}
        {result !== null && <ResultPanel result={result} />}

        <DialogFooter>
          {result === null ? (
            <>
              <Button
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={importing}
              >
                Cancel
              </Button>
              <Button onClick={handleImport} disabled={files.length === 0 || importing}>
                {importing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Uploading {files.length} {files.length === 1 ? "file" : "files"}...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    Upload &amp; Parse{files.length > 0 ? ` (${files.length})` : ""}
                  </>
                )}
              </Button>
            </>
          ) : (
            <Button onClick={handleDone}>Done</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Result panel - per-file results
// =============================================================================
function ResultPanel({ result }: { result: WorkforceMultiImportResponse }) {
  return (
    <div className="space-y-4 py-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {result.files_failed === 0 ? (
            <>
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
              <span className="font-medium">All files imported successfully</span>
            </>
          ) : (
            <>
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <span className="font-medium">
                {result.files_succeeded} of {result.files_total} files imported
              </span>
            </>
          )}
        </div>
        <div className="text-xs text-muted-foreground tabular-nums">
          {result.files_succeeded} ok / {result.files_failed} failed
        </div>
      </div>

      <div className="space-y-3">
        {result.results.map((r, i) => (
          <FileResultRow key={i} result={r} />
        ))}
      </div>
    </div>
  );
}

function FileResultRow({ result }: { result: WorkforceImportResponse }) {
  const warningsByCode: Record<string, WorkforceImportWarning[]> = {};
  for (const w of result.warnings) {
    if (!warningsByCode[w.code]) warningsByCode[w.code] = [];
    warningsByCode[w.code].push(w);
  }

  return (
    <div
      className={
        "border rounded-lg p-3 space-y-2 " +
        (result.success
          ? "border-foreground/8 bg-card/40"
          : "border-destructive/20 bg-destructive/5")
      }
    >
      <div className="flex items-start gap-2">
        {result.success ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
        ) : (
          <XCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate">
            {result.source_filename ?? "(unnamed)"}
          </div>
          {result.success && result.company_label && (
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
              <Building2 className="h-3 w-3" />
              <span className="font-medium text-foreground">{result.company_label}</span>
              <span>·</span>
              <span>{result.snapshot_date}</span>
              <span>·</span>
              <span>{result.rows_imported} rows</span>
              {result.positions_created > 0 && (
                <>
                  <span>·</span>
                  <span className="text-primary flex items-center gap-1">
                    <Sparkles className="h-3 w-3" />
                    {result.positions_created} new
                  </span>
                </>
              )}
            </div>
          )}
          {!result.success && (
            <div className="text-xs mt-2 p-2 rounded-md bg-destructive/10 border border-destructive/20">
              <div className="font-semibold text-destructive flex items-center gap-1.5 mb-1">
                <XCircle className="h-3.5 w-3.5" />
                File rejected
              </div>
              <div className="text-destructive/80">
                {result.error ?? "Unknown error"}
              </div>
            </div>
          )}
        </div>
      </div>

      {result.success && result.snapshot && (
        <div className="grid grid-cols-3 gap-2 text-xs pl-6">
          <Stat label="Direct" value={result.snapshot.direct_present} />
          <Stat label="Indirect" value={result.snapshot.indirect_present} />
          <Stat label="Subcontractor" value={result.snapshot.subcontractor_present} />
        </div>
      )}

      {result.success && Object.keys(warningsByCode).length > 0 && (
        <div className="space-y-1 pl-6 pt-1">
          {warningsByCode["GRAND_TOTAL_MISMATCH"] && (
            <WarningChip
              tone="amber"
              text={`Grand total mismatch: ${warningsByCode["GRAND_TOTAL_MISMATCH"][0].message}`}
            />
          )}
          {warningsByCode["SNAPSHOT_REPLACED"] && (
            <WarningChip tone="blue" text="Replaced existing snapshot" />
          )}
          {warningsByCode["UNKNOWN_POSITION_CREATED"] && (
            <WarningChip
              tone="indigo"
              text={`${warningsByCode["UNKNOWN_POSITION_CREATED"].length} new position${warningsByCode["UNKNOWN_POSITION_CREATED"].length === 1 ? "" : "s"} auto-created`}
            />
          )}
          {warningsByCode["POSITION_RESOLVE_FAILED"] && (
            <WarningChip
              tone="amber"
              text={`${warningsByCode["POSITION_RESOLVE_FAILED"].length} row(s) skipped`}
            />
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-card/60 rounded px-2 py-1.5 text-center">
      <div className="font-heading font-semibold tabular-nums">{value}</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
        {label}
      </div>
    </div>
  );
}

function WarningChip({
  tone,
  text,
}: {
  tone: "amber" | "blue" | "indigo";
  text: string;
}) {
  const tones: Record<typeof tone, string> = {
    amber: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    blue: "border-blue-500/20 bg-blue-500/10 text-blue-700 dark:text-blue-300",
    indigo: "border-primary/20 bg-primary/10 text-primary",
  };
  return (
    <div
      className={
        "inline-flex items-center gap-1 text-[11px] border rounded-full px-2 py-0.5 mr-1 " +
        tones[tone]
      }
    >
      <Info className="h-3 w-3" />
      {text}
    </div>
  );
}
