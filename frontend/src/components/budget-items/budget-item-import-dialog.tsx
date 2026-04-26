"use client";

import { useRef, useState } from "react";
import {
  FileSpreadsheet,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Info,
  X,
  AlertOctagon,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api-client";
import type {
  BudgetImportResult,
  BudgetImportMode,
} from "@/types/budget";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: number;
  onSuccess: () => void;
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

function isValidExcel(name: string): boolean {
  return name.toLowerCase().endsWith(".xlsx");
}

export function BudgetItemImportDialog({
  open,
  onOpenChange,
  projectId,
  onSuccess,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<BudgetImportMode>("append");
  const [confirmReplace, setConfirmReplace] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BudgetImportResult | null>(null);

  function reset() {
    setFile(null);
    setMode("append");
    setConfirmReplace(false);
    setError(null);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  function validateAndSetFile(candidate: File) {
    if (!isValidExcel(candidate.name)) {
      setError("Only .xlsx files are allowed");
      setFile(null);
      return;
    }
    if (candidate.size > MAX_FILE_SIZE) {
      setError("File size exceeds 5 MB");
      setFile(null);
      return;
    }
    setFile(candidate);
    setError(null);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (!selected) return;
    validateAndSetFile(selected);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    validateAndSetFile(dropped);
  }

  async function handleImport() {
    if (!file) {
      setError("Please select a file");
      return;
    }
    if (mode === "replace" && !confirmReplace) {
      setError("Please confirm replace mode by ticking the checkbox");
      return;
    }

    setImporting(true);
    setError(null);
    try {
      const res = await api.budgetItems.importExcel(projectId, file, mode);
      setResult(res);
      if (res.imported_count > 0 || res.deleted_count > 0) {
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  function handleImportAnother() {
    setFile(null);
    setResult(null);
    setError(null);
    setConfirmReplace(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // Result screen
  if (result) {
    return (
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Import Complete</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {result.deleted_count > 0 && (
              <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/30 p-4">
                <Info className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />
                <div>
                  <p className="font-medium text-blue-800 dark:text-blue-300">
                    {result.deleted_count} existing budget item
                    {result.deleted_count > 1 ? "s" : ""} replaced
                  </p>
                  <p className="text-xs text-blue-600 dark:text-blue-500">
                    Previous rows for this project were removed first.
                  </p>
                </div>
              </div>
            )}

            {result.imported_count > 0 && (
              <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30 p-4">
                <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0" />
                <div>
                  <p className="font-medium text-green-800 dark:text-green-300">
                    {result.imported_count} budget item
                    {result.imported_count > 1 ? "s" : ""} imported
                  </p>
                  <p className="text-xs text-green-600 dark:text-green-500">
                    Successfully added to the project
                  </p>
                </div>
              </div>
            )}

            {result.errors.length > 0 && (
              <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30 p-4">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0" />
                  <p className="font-medium text-red-800 dark:text-red-300">
                    {result.errors.length} error
                    {result.errors.length > 1 ? "s" : ""}
                  </p>
                </div>
                <div className="mt-3 max-h-40 overflow-y-auto text-xs space-y-1 text-red-700 dark:text-red-400">
                  {result.errors.map((err, i) => (
                    <p key={i}>
                      <span className="font-medium">Row {err.row}:</span>{" "}
                      {err.reason}
                    </p>
                  ))}
                </div>
              </div>
            )}

            {result.warnings.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30 p-4">
                <div className="flex items-center gap-3">
                  <Info className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
                  <p className="font-medium text-amber-800 dark:text-amber-300">
                    {result.warnings.length} warning
                    {result.warnings.length > 1 ? "s" : ""}
                  </p>
                </div>
                <div className="mt-3 max-h-40 overflow-y-auto text-xs space-y-1 text-amber-700 dark:text-amber-400">
                  {result.warnings.map((w, i) => (
                    <p key={i}>
                      <span className="font-medium">Row {w.row}:</span>{" "}
                      {w.reason}
                    </p>
                  ))}
                </div>
              </div>
            )}

            {result.imported_count === 0 &&
              result.deleted_count === 0 &&
              result.errors.length === 0 &&
              result.warnings.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No data was processed.
                </p>
              )}
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={handleImportAnother}>
              Import another file
            </Button>
            <Button onClick={() => handleOpenChange(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  // Upload screen
  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5" />
            Import Budget Items from Excel
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Drop zone */}
          <div
            className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 cursor-pointer transition-colors hover:border-primary/50 hover:bg-muted/30"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
          >
            {file ? (
              <div className="flex items-center gap-2 text-sm">
                <FileSpreadsheet className="h-5 w-5 text-green-600" />
                <span className="font-medium">{file.name}</span>
                <span className="text-muted-foreground">
                  ({(file.size / 1024).toFixed(0)} KB)
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ) : (
              <>
                <Upload className="h-8 w-8 text-muted-foreground" />
                <div className="text-center">
                  <p className="text-sm font-medium">
                    Drop your Excel file here or click to browse
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    .xlsx files up to 5 MB
                  </p>
                </div>
              </>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={handleFileChange}
            />
          </div>

          {/* Mode selector */}
          <div className="space-y-2">
            <Label>Import mode</Label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => {
                  setMode("append");
                  setConfirmReplace(false);
                }}
                className={`text-left rounded-lg border p-3 transition-colors ${
                  mode === "append"
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/30"
                }`}
              >
                <p className="text-sm font-medium">Append</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Add rows. Skip duplicates.
                </p>
              </button>
              <button
                type="button"
                onClick={() => setMode("replace")}
                className={`text-left rounded-lg border p-3 transition-colors ${
                  mode === "replace"
                    ? "border-destructive bg-destructive/5"
                    : "border-border hover:bg-muted/30"
                }`}
              >
                <p className="text-sm font-medium">Replace</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Wipe existing items first.
                </p>
              </button>
            </div>
          </div>

          {/* Replace warning */}
          {mode === "replace" && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-3 space-y-2">
              <div className="flex items-start gap-2">
                <AlertOctagon className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                <p className="text-xs text-destructive">
                  <span className="font-medium">Destructive operation.</span>{" "}
                  All existing budget items for this project will be permanently
                  deleted before the new ones are imported. Expenses linked to
                  those items will have their <code>budget_item_id</code> set to
                  null.
                </p>
              </div>
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmReplace}
                  onChange={(e) => setConfirmReplace(e.target.checked)}
                  className="accent-destructive"
                />
                <span>I understand and want to replace the budget.</span>
              </label>
            </div>
          )}

          {/* Column mapping hint */}
          <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground space-y-1">
            <p className="font-medium text-foreground">Expected columns:</p>
            <p>
              <span className="font-medium">Category</span> (Kategori /
              Категория),{" "}
              <span className="font-medium">Item</span> (Kalem /
              Наименование),{" "}
              <span className="font-medium">Amount</span> (Tutar / Сумма),{" "}
              <span className="font-medium">Notes</span> (Açıklama /
              Комментарий)
            </p>
            <p>
              Headers are matched automatically (TR / EN / RU). Unknown
              categories will be auto-created.
            </p>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={importing}
          >
            Cancel
          </Button>
          <Button
            onClick={handleImport}
            disabled={
              !file ||
              importing ||
              (mode === "replace" && !confirmReplace)
            }
            variant={mode === "replace" ? "destructive" : "default"}
          >
            {importing
              ? "Importing..."
              : mode === "replace"
              ? "Replace budget"
              : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
