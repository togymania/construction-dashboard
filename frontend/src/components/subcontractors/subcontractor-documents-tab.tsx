"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  Upload, FileText, Bot, Download, Trash2, ExternalLink, Plus,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ExtractedDataPreview } from "@/components/subcontractors/extracted-data-preview";
import { api } from "@/lib/api-client";
import { formatDate } from "@/lib/formatters";
import type {
  SubcontractorContract, ContractDocument as ContractDoc, DocumentType,
} from "@/types/subcontractor";

interface Props {
  subId: number;
  contracts: SubcontractorContract[] | null;
  canEdit: boolean;
}

interface DocWithContract extends ContractDoc {
  contract_number: string | null;
  contract_description: string;
}

export function SubcontractorDocumentsTab({ subId, contracts, canEdit }: Props) {
  const [docs, setDocs] = useState<DocWithContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadContractId, setUploadContractId] = useState<number | "">("");
  const [uploadType, setUploadType] = useState<DocumentType>("CONTRACT");
  const [uploading, setUploading] = useState(false);
  const [expandedDocId, setExpandedDocId] = useState<number | null>(null);

  const activeContracts = useMemo(() => contracts ?? [], [contracts]);

  // Auto-pick first contract once contracts load (so dropdown isn't empty)
  useEffect(() => {
    if (uploadContractId === "" && activeContracts.length > 0) {
      setUploadContractId(activeContracts[0]!.id);
    }
  }, [activeContracts, uploadContractId]);

  async function loadAll() {
    if (!contracts || contracts.length === 0) {
      setDocs([]); setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const all: DocWithContract[] = [];
      // Fetch documents for each contract in parallel
      const results = await Promise.all(
        contracts.map((c) =>
          api.subcontractors.documents.list(subId, c.id)
            .then((list) => list.map((d) => ({
              ...d,
              contract_number: c.contract_number,
              contract_description: c.description,
            })))
            .catch(() => [] as DocWithContract[])
        )
      );
      for (const list of results) all.push(...list);
      // Sort newest first
      all.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setDocs(all);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadAll(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [contracts, subId]);

  function handleDocUpdated(updated: ContractDoc) {
    setDocs((prev) => prev.map((d) => (d.id === updated.id ? { ...d, ...updated } : d)));
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!uploadContractId || typeof uploadContractId !== "number") {
      toast.error("Please select a contract first");
      e.target.value = "";
      return;
    }
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      const ok = confirm(
        "This file is not a PDF. AI extraction only runs on PDF or text files. Upload anyway?"
      );
      if (!ok) { e.target.value = ""; return; }
    }
    if (file.size > 100 * 1024 * 1024) {
      toast.error("File exceeds 100MB limit");
      e.target.value = "";
      return;
    }
    setUploading(true);
    try {
      await api.subcontractors.documents.upload(subId, uploadContractId, file, uploadType);
      toast.success("Uploaded — AI extraction complete");
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleDelete(doc: DocWithContract) {
    if (!confirm(`Delete ${doc.file_name}?`)) return;
    try {
      await api.subcontractors.documents.delete(doc.id);
      toast.success("Deleted");
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">Documents</h2>
          <p className="text-xs text-muted-foreground">
            Contract PDFs, invoices, and supporting documents. AI automatically extracts
            key fields after upload (mock — awaiting API key).
          </p>
        </div>
        {canEdit && activeContracts.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <Select value={String(uploadContractId)} onValueChange={(v) => setUploadContractId(Number(v))}>
              <SelectTrigger className="w-56"><SelectValue placeholder="Select contract" /></SelectTrigger>
              <SelectContent>
                {activeContracts.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.contract_number ?? `#${c.id}`} — {c.description.slice(0, 30)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={uploadType} onValueChange={(v) => setUploadType(v as DocumentType)}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="CONTRACT">Contract</SelectItem>
                <SelectItem value="INVOICE">Invoice</SelectItem>
                <SelectItem value="ADDENDUM">Addendum</SelectItem>
                <SelectItem value="REPORT">Report</SelectItem>
              </SelectContent>
            </Select>
            <Button asChild disabled={uploading}>
              <label className="cursor-pointer">
                <Upload className="h-4 w-4 mr-2" />
                {uploading ? "Uploading..." : "Upload PDF"}
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,application/pdf,text/plain"
                  onChange={handleUpload}
                  disabled={uploading}
                />
              </label>
            </Button>
          </div>
        )}
      </div>

      {!canEdit && (
        <div className="text-xs text-muted-foreground">
          Admin or Project Manager role required to upload documents.
        </div>
      )}

      {activeContracts.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>This subcontractor has no contracts yet. Create a contract from the
              Contracts tab first to upload documents.</p>
          </CardContent>
        </Card>
      )}

      {activeContracts.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            {loading ? (
              <div className="h-[120px] animate-pulse bg-muted/30 rounded" />
            ) : docs.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p>No documents yet. Use the Upload PDF button above to get started.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>File</TableHead>
                    <TableHead>Contract</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Uploaded</TableHead>
                    <TableHead className="w-32"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {docs.map((doc) => (
                    <Fragment key={doc.id}>
                      <TableRow>
                        <TableCell className="font-medium">
                          <button
                            type="button"
                            onClick={() => setExpandedDocId(expandedDocId === doc.id ? null : doc.id)}
                            className="text-left hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors flex items-center gap-1.5"
                          >
                            {doc.extracted_data ? (
                              <Bot className="h-3.5 w-3.5 text-indigo-500 flex-shrink-0" />
                            ) : (
                              <FileText className="h-3.5 w-3.5 flex-shrink-0 opacity-50" />
                            )}
                            {doc.file_name}
                          </button>
                        </TableCell>
                        <TableCell className="text-xs">
                          <Link
                            href={`/subcontractors/${subId}/contracts/${doc.contract_id}`}
                            className="text-indigo-600 dark:text-indigo-400 hover:underline inline-flex items-center gap-1"
                          >
                            {doc.contract_number ?? `#${doc.contract_id}`}
                            <ExternalLink className="h-2.5 w-2.5" />
                          </Link>
                        </TableCell>
                        <TableCell>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-muted">{doc.file_type}</span>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{(doc.file_size / 1024).toFixed(1)} KB</TableCell>
                        <TableCell className="text-xs">{formatDate(doc.created_at)}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <a href={api.subcontractors.documents.download(doc.id)} target="_blank" rel="noreferrer">
                              <Button variant="ghost" size="icon" className="h-7 w-7" title="Download">
                                <Download className="h-3.5 w-3.5" />
                              </Button>
                            </a>
                            {canEdit && (
                              <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => handleDelete(doc)} title="Delete">
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                      {expandedDocId === doc.id && (
                        <TableRow>
                          <TableCell colSpan={6} className="bg-muted/20 p-3">
                            <ExtractedDataPreview doc={doc} canEdit={canEdit} onUpdated={handleDocUpdated} />
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
