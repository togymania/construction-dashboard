"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Sparkles, AlertTriangle, Calendar, ScrollText, RefreshCw, Pencil,
  ShieldAlert, FileText, X, Save,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import { formatRubCompact } from "@/lib/formatters";
import type { ContractDocument, ExtractedContractData } from "@/types/subcontractor";

interface Props {
  doc: ContractDocument;
  canEdit: boolean;
  onUpdated: (updated: ContractDocument) => void;
}

export function ExtractedDataPreview({ doc, canEdit, onUpdated }: Props) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ExtractedContractData | null>(
    (doc.extracted_data as ExtractedContractData | null) ?? null
  );

  const data = (doc.extracted_data as ExtractedContractData | null) ?? null;

  if (!data) {
    return (
      <div className="text-xs text-muted-foreground p-3 rounded-lg bg-muted/30 border border-dashed flex items-center gap-2">
        <FileText className="h-3.5 w-3.5" />
        No data has been extracted from this document yet.
        {canEdit && (
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-2 text-xs ml-auto"
            onClick={async () => {
              setBusy(true);
              try {
                const updated = await api.subcontractors.documents.reExtract(doc.id);
                toast.success("Re-extracted");
                onUpdated(updated);
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Re-extract failed");
              } finally { setBusy(false); }
            }}
            disabled={busy}
          >
            <RefreshCw className={`h-3 w-3 mr-1 ${busy ? "animate-spin" : ""}`} /> Extract
          </Button>
        )}
      </div>
    );
  }

  async function handleReExtract() {
    setBusy(true);
    try {
      const updated = await api.subcontractors.documents.reExtract(doc.id);
      toast.success("Re-extracted");
      onUpdated(updated);
      setDraft(updated.extracted_data as ExtractedContractData | null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Re-extract failed");
    } finally { setBusy(false); }
  }

  async function handleSave() {
    if (!draft) return;
    setBusy(true);
    try {
      const updated = await api.subcontractors.documents.updateExtracted(
        doc.id,
        draft as unknown as Record<string, unknown>,
      );
      toast.success("Saved");
      onUpdated(updated);
      setEditing(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally { setBusy(false); }
  }

  const sourceLabel = data.source === "llm" ? "LLM"
    : data.source === "llm_mock" ? "LLM (mock — awaiting API key)"
    : data.source === "user_edited" ? "User edited"
    : "Regex";

  const confidencePct = Math.round((data.confidence ?? 0) * 100);
  const confidenceColor = (data.confidence ?? 0) >= 0.7
    ? "text-emerald-600 dark:text-emerald-400"
    : (data.confidence ?? 0) >= 0.4 ? "text-amber-600 dark:text-amber-400"
    : "text-red-600 dark:text-red-400";

  return (
    <Card className="border-indigo-200 dark:border-indigo-900 bg-indigo-50/30 dark:bg-indigo-950/10">
      <CardHeader className="pb-2 flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-indigo-500" /> Extracted Data
          <span className={`text-[10px] font-normal px-1.5 py-0.5 rounded bg-muted ${confidenceColor}`}>
            {sourceLabel} · {confidencePct}%
          </span>
        </CardTitle>
        {canEdit && (
          <div className="flex items-center gap-1">
            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleReExtract} disabled={busy} title="Re-extract">
              <RefreshCw className={`h-3 w-3 ${busy ? "animate-spin" : ""}`} />
            </Button>
            {!editing ? (
              <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setEditing(true)} title="Edit">
                <Pencil className="h-3 w-3" />
              </Button>
            ) : (
              <>
                <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleSave} disabled={busy}>
                  <Save className="h-3 w-3 mr-1" /> Save
                </Button>
                <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => { setEditing(false); setDraft(data); }}>
                  <X className="h-3 w-3" />
                </Button>
              </>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        {/* Summary line */}
        {data.summary && (
          <div className="text-sm leading-relaxed text-foreground/90">{data.summary}</div>
        )}

        {/* Key/value grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          <KV label="Contract amount" value={
            data.contract_amount
              ? `${formatRubCompact(parseFloat(data.contract_amount))} ${data.currency ?? ""}`.trim()
              : null
          } editing={editing} draftKey="contract_amount" draft={draft} setDraft={setDraft} />
          <KV label="Currency" value={data.currency} editing={editing} draftKey="currency" draft={draft} setDraft={setDraft} />
          <KV label="Start date" value={data.start_date} editing={editing} draftKey="start_date" draft={draft} setDraft={setDraft} />
          <KV label="End date" value={data.end_date} editing={editing} draftKey="end_date" draft={draft} setDraft={setDraft} />
          <KV label="Subcontractor" value={data.company_name} editing={editing} draftKey="company_name" draft={draft} setDraft={setDraft} />
          <KV label="Main contractor" value={data.counterparty_name} editing={editing} draftKey="counterparty_name" draft={draft} setDraft={setDraft} />
        </div>

        {data.payment_terms_summary && (
          <div className="text-foreground/80 italic">
            <ScrollText className="h-3 w-3 inline mr-1" />
            Payment: {data.payment_terms_summary}
          </div>
        )}

        {/* Penalty clauses */}
        {data.penalty_clauses && data.penalty_clauses.length > 0 && (
          <div className="space-y-1">
            <div className="font-semibold text-foreground/80 flex items-center gap-1">
              <ShieldAlert className="h-3 w-3 text-red-500" /> Penalty Clauses
            </div>
            {data.penalty_clauses.map((p, i) => (
              <div key={i} className="pl-4 text-muted-foreground border-l-2 border-red-300 dark:border-red-700">
                <strong>{p.trigger}:</strong>{" "}
                {p.percentage !== null && p.percentage !== undefined ? `${p.percentage}%` : ""}
                {p.amount ? ` ${p.amount}` : ""} — {p.description}
              </div>
            ))}
          </div>
        )}

        {/* Key dates */}
        {data.key_dates && data.key_dates.length > 0 && (
          <div className="space-y-1">
            <div className="font-semibold text-foreground/80 flex items-center gap-1">
              <Calendar className="h-3 w-3 text-indigo-500" /> Key Dates
            </div>
            {data.key_dates.map((d, i) => (
              <div key={i} className="pl-4 text-muted-foreground">
                <strong>{d.date}</strong> — {d.label}
                {d.description ? `: ${d.description}` : ""}
              </div>
            ))}
          </div>
        )}

        {/* Risk flags */}
        {data.risk_flags && data.risk_flags.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {data.risk_flags.map((f, i) => (
              <span key={i} className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border border-amber-300 dark:border-amber-700 bg-amber-100/50 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200">
                <AlertTriangle className="h-2.5 w-2.5" /> {f}
              </span>
            ))}
          </div>
        )}

        {data.source === "llm_mock" && (
          <div className="flex items-start gap-2 p-2 rounded border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 text-[11px] text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
            <span>
              These values are mock data. Real LLM calls will be made once
              ANTHROPIC_API_KEY is added to the .env file. Click &quot;Re-extract&quot;
              on this document to trigger the real extraction.
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function KV({
  label, value, editing, draftKey, draft, setDraft,
}: {
  label: string;
  value: string | null | undefined;
  editing: boolean;
  draftKey: keyof ExtractedContractData;
  draft: ExtractedContractData | null;
  setDraft: (d: ExtractedContractData) => void;
}) {
  if (editing && draft) {
    const current = (draft[draftKey] as string | null | undefined) ?? "";
    return (
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
        <input
          className="text-xs rounded border bg-background px-2 py-1"
          value={current ?? ""}
          onChange={(e) => setDraft({ ...draft, [draftKey]: e.target.value || null } as ExtractedContractData)}
        />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="font-medium">{value || <span className="text-muted-foreground/60 italic">—</span>}</span>
    </div>
  );
}
