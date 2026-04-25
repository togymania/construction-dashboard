"use client";

import { useRef, useState } from "react";
import { FileSpreadsheet, Upload, CheckCircle2, AlertTriangle, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api-client";
import type { BudgetCategory, ExpenseImportResult } from "@/types/budget";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: number;
  categories: BudgetCategory[];
  onSuccess: () => void;
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

export function ExpenseImportDialog({
  open,
  onOpenChange,
  projectId,
  categories,
  onSuccess,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [categoryId, setCategoryId] = useState("");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExpenseImportResult | null>(null);

  function reset() {
    setFile(null);
    setCategoryId(categories.length > 0 ? String(categories[0].id) : "");
    setError(null);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (
      !selected.name.endsWith(".xlsx") &&
      !selected.name.endsWith(".xls")
    ) {
      setError("Only .xlsx files are allowed");
      setFile(null);
      return;
    }
    if (selected.size > MAX_FILE_SIZE) {
      setError("File size exceeds 5 MB");
      setFile(null);
      return;
    }
    setFile(selected);
    setError(null);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    if (!dropped.name.endsWith(".xlsx")) {
      setError("Only .xlsx files are allowed");
      return;
    }
    if (dropped.size > MAX_FILE_SIZE) {
      setError("File size exceeds 5 MB");
      return;
    }
    setFile(dropped);
    setError(null);
  }

  async function handleImport() {
    if (!file) {
      setError("Please select a file");
      return;
    }
    if (!categoryId) {
      setError("Please select a default category");
      return;
    }

    setImporting(true);
    setError(null);
    try {
      const res = await api.expenses.importExcel(
        projectId,
        file,
        parseInt(categoryId, 10)
      );
      setResult(res);
      if (res.imported_count > 0) {
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  const activeCategories = categories.filter((c) => c.is_active);

  // Result screen
  if (result) {
    return (
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Import Complete</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {result.imported_count > 0 && (
              <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30 p-4">
                <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0" />
                <div>
                  <p className="font-medium text-green-800 dark:text-green-300">
                    {result.imported_count} expense{result.imported_count > 1 ? "s" : ""} imported
                  </p>
                  <p className="text-xs text-green-600 dark:text-green-500">
                    Successfully added to the project
                  </p>
                </div>
              </div>
            )}

            {result.skipped_count > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30 p-4">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
                  <p className="font-medium text-amber-800 dark:text-amber-300">
                    {result.skipped_count} row{result.skipped_count > 1 ? "s" : ""} skipped
                  </p>
                </div>
                {result.errors.length > 0 && (
                  <div className="mt-3 max-h-40 overflow-y-auto text-xs space-y-1 text-amber-700 dark:text-amber-400">
                    {result.errors.map((err, i) => (
                      <p key={i}>
                        <span className="font-medium">Row {err.row}:</span>{" "}
                        {err.reason}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {result.imported_count === 0 && result.skipped_count === 0 && (
              <p className="text-sm text-muted-foreground">No data was processed.</p>
            )}
          </div>

          <DialogFooter>
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
            Import Expenses from Excel
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
              accept=".xlsx,.xls"
              className="hidden"
              onChange={handleFileChange}
            />
          </div>

          {/* Default category */}
          <div className="space-y-2">
            <Label htmlFor="import-category">
              Default Category{" "}
              <span className="text-muted-foreground text-xs">
                (used when category is missing or unrecognized)
              </span>
            </Label>
            <Select value={categoryId} onValueChange={setCategoryId}>
              <SelectTrigger id="import-category">
                <SelectValue placeholder="Select category" />
              </SelectTrigger>
              <SelectContent>
                {activeCategories.map((cat) => (
                  <SelectItem key={cat.id} value={String(cat.id)}>
                    {cat.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Column mapping hint */}
          <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground space-y-1">
            <p className="font-medium text-foreground">Expected columns:</p>
            <p>
              <span className="font-medium">Vendor</span> (Company / Şirket),{" "}
              <span className="font-medium">Invoice No</span> (Fatura No),{" "}
              <span className="font-medium">Date</span> (Tarih),{" "}
              <span className="font-medium">Amount</span> (Tutar),{" "}
              <span className="font-medium">Category</span> (Kategori),{" "}
              <span className="font-medium">Description</span> (Açıklama)
            </p>
            <p>Column headers are matched automatically (TR &amp; EN supported).</p>
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
            disabled={!file || !categoryId || importing}
          >
            {importing ? "Importing..." : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
