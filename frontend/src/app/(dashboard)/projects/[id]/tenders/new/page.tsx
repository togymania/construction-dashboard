"use client";

import { useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Upload,
  FileSpreadsheet,
  Sparkles,
  ArrowLeft,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api-client";
import { useT } from "@/lib/i18n/provider";
import type {
  ExtractedBid,
  ExtractedBidLine,
  ExtractedLineItem,
  TenderExtraction,
} from "@/types/tender";

// ---------------------------------------------------------------------------
// Form state mirrors TenderExtraction so we can pre-fill from the upload step
// or start blank for manual entry.
// ---------------------------------------------------------------------------

interface DraftState {
  title: string;
  object_name: string;
  currency: string;
  payment_terms_expected: string;
  delivery_terms_expected: string;
  notes: string;
  line_items: ExtractedLineItem[];
  bids: ExtractedBid[];
  warnings: string[];
  source: "llm" | "rule" | "blank";
}

function blankDraft(): DraftState {
  return {
    title: "",
    object_name: "",
    currency: "RUB",
    payment_terms_expected: "",
    delivery_terms_expected: "",
    notes: "",
    line_items: [
      { order_num: 1, description: "", unit: "", quantity: "0" },
    ],
    bids: [],
    warnings: [],
    source: "blank",
  };
}

function fromExtraction(x: TenderExtraction): DraftState {
  return {
    title: x.title,
    object_name: x.object_name ?? "",
    currency: x.currency || "RUB",
    payment_terms_expected: x.payment_terms_expected ?? "",
    delivery_terms_expected: x.delivery_terms_expected ?? "",
    notes: x.notes ?? "",
    line_items: x.line_items.length
      ? x.line_items
      : [{ order_num: 1, description: "", unit: "", quantity: "0" }],
    bids: x.bids,
    warnings: x.warnings || [],
    source: x.source,
  };
}

export default function NewTenderPage() {
  const params = useParams<{ id: string }>();
  const projectId = parseInt(params.id, 10);
  const router = useRouter();
  const { t } = useT();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<"choose" | "edit">("choose");
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<DraftState>(blankDraft);

  async function handleFile(file: File) {
    setExtracting(true);
    try {
      const result = await api.tenders.extract(projectId, file);
      setDraft(fromExtraction(result));
      setStep("edit");
      if (result.warnings.length > 0) {
        toast.warning(`${result.warnings.length} warning(s) — review the draft`);
      } else {
        toast.success("File analyzed — review and save");
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Extraction failed");
    } finally {
      setExtracting(false);
    }
  }

  async function handleSave() {
    if (!draft.title.trim()) {
      toast.error("Title is required");
      return;
    }
    setSaving(true);
    try {
      // 1. Create the tender with line items
      const tender = await api.tenders.create(projectId, {
        title: draft.title.trim(),
        object_name: draft.object_name || null,
        currency: draft.currency || "RUB",
        payment_terms_expected: draft.payment_terms_expected || null,
        delivery_terms_expected: draft.delivery_terms_expected || null,
        notes: draft.notes || null,
        line_items: draft.line_items
          .filter((li) => li.description.trim())
          .map((li, idx) => ({
            order_num: idx + 1,
            description: li.description.trim(),
            unit: li.unit || null,
            quantity: li.quantity || "0",
            notes: null,
          })),
      });

      // 2. Map order_num → real tender_line_item_id
      const idByOrder = new Map<number, number>();
      tender.line_items.forEach((li) => idByOrder.set(li.order_num, li.id));

      // 3. Create each bid with line prices
      for (const b of draft.bids) {
        await api.tenders.createBid(tender.id, {
          company_name: b.company_name,
          contact_name: b.contact_name,
          contact_phone: b.contact_phone,
          contact_email: b.contact_email,
          included_in_price: b.included_in_price,
          not_included_in_price: b.not_included_in_price,
          payment_terms: b.payment_terms,
          delivery_days: b.delivery_days,
          notes: b.notes,
          line_items: b.lines
            .map((bl) => {
              const lineId = idByOrder.get(bl.order_num);
              if (!lineId) return null;
              return {
                tender_line_item_id: lineId,
                unit_price_labor: bl.unit_price_labor ?? null,
                unit_price_material: bl.unit_price_material ?? null,
                unit_price_total: bl.unit_price_total ?? "0",
              };
            })
            .filter((x): x is NonNullable<typeof x> => x !== null),
        });
      }

      toast.success("Tender saved");
      router.push(`/projects/${projectId}/tenders/${tender.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  // -------------------- Render --------------------

  if (step === "choose") {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectId}/tenders`)}
          >
            <ArrowLeft className="mr-1 h-4 w-4" /> Back
          </Button>
          <h1 className="text-2xl font-semibold">
            {t("tenders.newTender") || "New Tender"}
          </h1>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Card
            className="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md"
            onClick={() => fileInputRef.current?.click()}
          >
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 p-2 text-white">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle className="text-base">
                    {t("tenders.upload") || "Upload Excel/PDF"}
                  </CardTitle>
                  <CardDescription>
                    AI extracts line items, prices, bidders
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Drop a КП Форма, Teklif Karşılaştırma Formu, or any bidder
                quotation file. The AI will parse the work items and every
                company's prices into an editable draft.
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xlsm,.pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                  // reset so user can re-upload same file
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
              />
              {extracting ? (
                <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("tenders.analyzing") || "Analyzing file…"}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md"
            onClick={() => {
              setDraft(blankDraft());
              setStep("edit");
            }}
          >
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-slate-500/10 p-2 text-slate-700 dark:text-slate-300">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle className="text-base">
                    {t("tenders.manual") || "Manual entry"}
                  </CardTitle>
                  <CardDescription>
                    Type the work items and bids yourself
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Start with a blank form when you have the prices in hand and
                want to enter them directly.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // ----------------------- Edit step -----------------------

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setStep("choose")}
          >
            <ArrowLeft className="mr-1 h-4 w-4" /> Back
          </Button>
          <h1 className="text-2xl font-semibold">
            {draft.source === "llm" ? "Review extracted draft" : "New tender"}
          </h1>
          {draft.source === "llm" ? (
            <Badge variant="default">
              <Sparkles className="mr-1 h-3 w-3" /> AI draft
            </Badge>
          ) : null}
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <>
              <Loader2 className="mr-1 h-4 w-4 animate-spin" /> Saving…
            </>
          ) : (
            <>
              <Upload className="mr-1 h-4 w-4" /> Save tender
            </>
          )}
        </Button>
      </div>

      {draft.warnings.length > 0 ? (
        <Card className="border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-900">
          <CardContent className="space-y-1 py-3 text-sm text-amber-900 dark:text-amber-200">
            <strong>AI flagged for review:</strong>
            <ul className="ml-4 list-disc">
              {draft.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {/* ---------- Header / meta ---------- */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tender header</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <Label htmlFor="title">Title *</Label>
            <Input
              id="title"
              value={draft.title}
              onChange={(e) =>
                setDraft((d) => ({ ...d, title: e.target.value }))
              }
              placeholder="Karot, Pencere doğraması…"
            />
          </div>
          <div>
            <Label htmlFor="object">Object / building</Label>
            <Input
              id="object"
              value={draft.object_name}
              onChange={(e) =>
                setDraft((d) => ({ ...d, object_name: e.target.value }))
              }
            />
          </div>
          <div>
            <Label htmlFor="currency">Currency</Label>
            <Input
              id="currency"
              value={draft.currency}
              onChange={(e) =>
                setDraft((d) => ({ ...d, currency: e.target.value }))
              }
            />
          </div>
          <div>
            <Label htmlFor="pay">Expected payment terms</Label>
            <Input
              id="pay"
              value={draft.payment_terms_expected}
              onChange={(e) =>
                setDraft((d) => ({
                  ...d,
                  payment_terms_expected: e.target.value,
                }))
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* ---------- Line items ---------- */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Line items (metraj)</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              setDraft((d) => ({
                ...d,
                line_items: [
                  ...d.line_items,
                  {
                    order_num: d.line_items.length + 1,
                    description: "",
                    unit: "",
                    quantity: "0",
                  },
                ],
              }))
            }
          >
            <Plus className="mr-1 h-4 w-4" /> Add row
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {draft.line_items.map((li, idx) => (
            <div
              key={idx}
              className="grid grid-cols-12 items-center gap-2 rounded border bg-card p-2"
            >
              <div className="col-span-1 text-center text-sm text-muted-foreground">
                {idx + 1}
              </div>
              <Input
                className="col-span-6"
                placeholder="Description"
                value={li.description}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    line_items: d.line_items.map((x, i) =>
                      i === idx ? { ...x, description: e.target.value } : x,
                    ),
                  }))
                }
              />
              <Input
                className="col-span-2"
                placeholder="Unit"
                value={li.unit ?? ""}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    line_items: d.line_items.map((x, i) =>
                      i === idx ? { ...x, unit: e.target.value } : x,
                    ),
                  }))
                }
              />
              <Input
                className="col-span-2"
                type="number"
                step="any"
                placeholder="Qty"
                value={li.quantity?.toString() ?? "0"}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...d,
                    line_items: d.line_items.map((x, i) =>
                      i === idx ? { ...x, quantity: e.target.value } : x,
                    ),
                  }))
                }
              />
              <Button
                variant="ghost"
                size="sm"
                className="col-span-1"
                onClick={() =>
                  setDraft((d) => ({
                    ...d,
                    line_items: d.line_items.filter((_, i) => i !== idx),
                  }))
                }
              >
                <Trash2 className="h-4 w-4 text-rose-500" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* ---------- Bids ---------- */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Bidders ({draft.bids.length})</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              setDraft((d) => ({
                ...d,
                bids: [
                  ...d.bids,
                  {
                    company_name: "",
                    contact_name: null,
                    contact_phone: null,
                    contact_email: null,
                    included_in_price: null,
                    not_included_in_price: null,
                    payment_terms: null,
                    delivery_days: null,
                    notes: null,
                    lines: [],
                  },
                ],
              }))
            }
          >
            <Plus className="mr-1 h-4 w-4" /> Add bidder
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {draft.bids.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No bidders yet. You can add them now or later from the tender
              detail page.
            </p>
          ) : (
            draft.bids.map((b, bi) => (
              <div
                key={bi}
                className="rounded-md border p-3"
              >
                <div className="mb-2 flex items-center gap-2">
                  <Input
                    value={b.company_name}
                    placeholder="Company name *"
                    className="font-medium"
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        bids: d.bids.map((x, i) =>
                          i === bi ? { ...x, company_name: e.target.value } : x,
                        ),
                      }))
                    }
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setDraft((d) => ({
                        ...d,
                        bids: d.bids.filter((_, i) => i !== bi),
                      }))
                    }
                  >
                    <Trash2 className="h-4 w-4 text-rose-500" />
                  </Button>
                </div>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                  <Input
                    placeholder="Contact"
                    value={b.contact_name ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        bids: d.bids.map((x, i) =>
                          i === bi ? { ...x, contact_name: e.target.value || null } : x,
                        ),
                      }))
                    }
                  />
                  <Input
                    placeholder="Delivery (days)"
                    type="number"
                    value={b.delivery_days ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        bids: d.bids.map((x, i) =>
                          i === bi
                            ? {
                                ...x,
                                delivery_days: e.target.value
                                  ? parseInt(e.target.value, 10)
                                  : null,
                              }
                            : x,
                        ),
                      }))
                    }
                  />
                  <Input
                    placeholder="Payment terms"
                    value={b.payment_terms ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        bids: d.bids.map((x, i) =>
                          i === bi ? { ...x, payment_terms: e.target.value || null } : x,
                        ),
                      }))
                    }
                  />
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {b.lines.length} priced line{b.lines.length === 1 ? "" : "s"} —
                  edit prices on the tender detail page after saving.
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
