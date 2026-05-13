"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Sparkles,
  Trophy,
  Loader2,
  Plus,
  Trash2,
  Upload,
  X,
  TrendingDown,
  TrendingUp,
  Info,
  Layers,
  ChevronRight,
  ChevronDown,
  HelpCircle,
} from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api-client";
import { formatRubCompact } from "@/lib/formatters";
import type {
  Bid,
  BidLineItem,
  ExtractedBid,
  MarketPriceEstimate,
  Tender,
  TenderLineItem,
  TenderMarketPrices,
} from "@/types/tender";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtCurrency(value: string | number | null | undefined, currency: string): string {
  if (value === null || value === undefined) return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  const compact = formatRubCompact(n);
  if (currency && currency !== "RUB") {
    return compact.replace("₽", currency);
  }
  return compact;
}

function fmtNum(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n) || n === 0) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function pct(a: number, b: number): number {
  if (!b) return 0;
  return ((a - b) / b) * 100;
}

/**
 * Map a price within [min, max] into a Tailwind background class.
 * Greenest at the minimum, reddest at the maximum, neutral mid-range.
 */
function cellTone(value: number | null, min: number, max: number): string {
  if (value === null || value === 0 || !isFinite(value)) return "";
  if (min === max) return "";
  const span = max - min;
  const ratio = (value - min) / span; // 0 = best, 1 = worst
  if (ratio <= 0.2) return "bg-emerald-50 dark:bg-emerald-950/30";
  if (ratio <= 0.5) return "bg-lime-50/60 dark:bg-lime-950/20";
  if (ratio <= 0.8) return "bg-amber-50/60 dark:bg-amber-950/20";
  return "bg-rose-50 dark:bg-rose-950/30";
}

interface HierarchyNode {
  line: TenderLineItem;
  depth: number;
  children: HierarchyNode[];
}

function buildHierarchy(items: TenderLineItem[]): HierarchyNode[] {
  const byId = new Map<number, HierarchyNode>();
  for (const li of items) {
    byId.set(li.id, { line: li, depth: 0, children: [] });
  }
  const roots: HierarchyNode[] = [];
  for (const node of byId.values()) {
    if (node.line.parent_id && byId.has(node.line.parent_id)) {
      const parent = byId.get(node.line.parent_id)!;
      node.depth = parent.depth + 1;
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }
  // sort children by order_num
  const sortKids = (n: HierarchyNode) => {
    n.children.sort((a, b) => a.line.order_num - b.line.order_num);
    n.children.forEach(sortKids);
  };
  roots.sort((a, b) => a.line.order_num - b.line.order_num);
  roots.forEach(sortKids);
  return roots;
}

function flattenHierarchy(
  nodes: HierarchyNode[],
  collapsed: Set<number>,
): HierarchyNode[] {
  const out: HierarchyNode[] = [];
  const walk = (ns: HierarchyNode[]) => {
    for (const n of ns) {
      out.push(n);
      if (n.children.length && !collapsed.has(n.line.id)) {
        // Re-anchor depth so children always render at parent.depth + 1
        n.children.forEach((c) => (c.depth = n.depth + 1));
        walk(n.children);
      }
    }
  };
  walk(nodes);
  return out;
}

function priceTypeBadge(pt: string, raw: string | null | undefined): string {
  const map: Record<string, string> = {
    negotiable: "Договорная",
    not_included: "Не включена",
    on_request: "По запросу",
  };
  return raw || map[pt] || pt;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TenderDetailPage() {
  const params = useParams<{ id: string; tid: string }>();
  const projectId = parseInt(params.id, 10);
  const tenderId = parseInt(params.tid, 10);
  const router = useRouter();

  const [tender, setTender] = useState<Tender | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [awarding, setAwarding] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [extracting, setExtracting] = useState(false);
  const [draft, setDraft] = useState<ExtractedBid | null>(null);
  const [savingBid, setSavingBid] = useState(false);
  const [viewMode, setViewMode] = useState<"simple" | "detailed">("simple");
  const [showMarketBox, setShowMarketBox] = useState(false);
  const [marketPrices, setMarketPrices] = useState<TenderMarketPrices | null>(null);
  const [marketLoading, setMarketLoading] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

  async function load() {
    try {
      const data = await api.tenders.get(tenderId);
      setTender(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load tender");
    }
  }

  async function loadMarket() {
    if (marketPrices || marketLoading) return;
    setMarketLoading(true);
    try {
      const data = await api.tenders.marketPrices(tenderId);
      setMarketPrices(data);
    } catch (e) {
      toast.error(
        e instanceof ApiError ? e.message : "Market price lookup failed",
      );
    } finally {
      setMarketLoading(false);
    }
  }

  async function handleBidFile(file: File) {
    setExtracting(true);
    try {
      const result = await api.tenders.extractBid(tenderId, file);
      setDraft(result);
      toast.success(`Extracted: ${result.company_name}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Extraction failed");
    } finally {
      setExtracting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function startManualBid() {
    if (!tender) return;
    setDraft({
      company_name: "",
      variant_label: null,
      vat_rate: "20",
      total_without_vat: null,
      total_with_vat: null,
      contact_name: null,
      contact_phone: null,
      contact_email: null,
      included_in_price: null,
      not_included_in_price: null,
      payment_terms: null,
      delivery_days: null,
      notes: null,
      lines: tender.line_items.map((li) => ({
        order_num: li.order_num,
        unit_price_labor: null,
        unit_price_material: null,
        unit_price_total: "0",
        price_type: "fixed",
        raw_text_price: null,
      })),
    });
  }

  async function saveDraftBid() {
    if (!draft || !tender) return;
    if (!draft.company_name.trim()) {
      toast.error("Company name is required");
      return;
    }
    setSavingBid(true);
    try {
      const idByOrder = new Map<number, number>();
      tender.line_items.forEach((li) => idByOrder.set(li.order_num, li.id));

      await api.tenders.createBid(tender.id, {
        company_name: draft.company_name.trim(),
        variant_label: draft.variant_label || null,
        vat_rate: draft.vat_rate || "20",
        contact_name: draft.contact_name,
        contact_phone: draft.contact_phone,
        contact_email: draft.contact_email,
        included_in_price: draft.included_in_price,
        not_included_in_price: draft.not_included_in_price,
        payment_terms: draft.payment_terms,
        delivery_days: draft.delivery_days,
        notes: draft.notes,
        line_items: draft.lines
          .map((bl) => {
            const lineId = idByOrder.get(bl.order_num);
            if (!lineId) return null;
            return {
              tender_line_item_id: lineId,
              unit_price_labor: bl.unit_price_labor ?? null,
              unit_price_material: bl.unit_price_material ?? null,
              unit_price_total: bl.unit_price_total ?? "0",
              price_type: bl.price_type ?? "fixed",
              raw_text_price: bl.raw_text_price ?? null,
            };
          })
          .filter((x): x is NonNullable<typeof x> => x !== null),
      });
      toast.success("Bid added");
      setDraft(null);
      setMarketPrices(null); // invalidate market cache trigger
      load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSavingBid(false);
    }
  }

  async function handleDeleteTender() {
    if (!confirm("Delete this tender and all its bids? This cannot be undone.")) return;
    try {
      await api.tenders.delete(tenderId);
      toast.success("Tender deleted");
      router.push(`/projects/${projectId}/tenders`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Delete failed");
    }
  }

  useEffect(() => {
    if (tenderId > 0) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenderId]);

  async function handleAward(bidId: number) {
    setAwarding(bidId);
    try {
      const updated = await api.tenders.award(tenderId, bidId);
      setTender(updated);
      toast.success("Bid awarded");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Award failed");
    } finally {
      setAwarding(null);
    }
  }

  async function handleDeleteBid(bidId: number) {
    if (!confirm("Delete this bid?")) return;
    try {
      await api.tenders.deleteBid(bidId);
      toast.success("Bid removed");
      load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Delete failed");
    }
  }

  function toggleCollapse(id: number) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // ---------- Derived ----------

  const hierarchy = useMemo(
    () => (tender ? buildHierarchy(tender.line_items) : []),
    [tender],
  );
  const visibleNodes = useMemo(
    () => flattenHierarchy(hierarchy, collapsed),
    [hierarchy, collapsed],
  );

  // Lookup bid_lines by (bidId, tender_line_item_id)
  const cellLookup = useMemo(() => {
    const map: Record<number, Record<number, BidLineItem | undefined>> = {};
    if (!tender) return map;
    for (const b of tender.bids) {
      map[b.id] = {};
      for (const bl of b.line_items) {
        map[b.id][bl.tender_line_item_id] = bl;
      }
    }
    return map;
  }, [tender]);

  // For each line: min/max across all bids (fixed prices only) so we
  // can color cells on a gradient.
  const lineExtremes = useMemo(() => {
    const out: Record<number, { min: number; max: number }> = {};
    if (!tender) return out;
    for (const li of tender.line_items) {
      const values: number[] = [];
      for (const b of tender.bids) {
        const cell = cellLookup[b.id]?.[li.id];
        if (!cell || cell.price_type !== "fixed") continue;
        const v = parseFloat(cell.unit_price_total);
        if (isFinite(v) && v > 0) values.push(v);
      }
      if (values.length >= 2) {
        out[li.id] = {
          min: Math.min(...values),
          max: Math.max(...values),
        };
      }
    }
    return out;
  }, [tender, cellLookup]);

  // Bidder totals min/max for the bidder cards
  const bidExtremes = useMemo(() => {
    if (!tender || tender.bids.length === 0)
      return { min: 0, max: 0, avg: 0 };
    const totals = tender.bids
      .map((b) => parseFloat(b.total_amount))
      .filter((n) => isFinite(n) && n > 0);
    if (totals.length === 0) return { min: 0, max: 0, avg: 0 };
    const sum = totals.reduce((a, b) => a + b, 0);
    return {
      min: Math.min(...totals),
      max: Math.max(...totals),
      avg: sum / totals.length,
    };
  }, [tender]);

  // Market prices keyed by tender_line_item_id
  const marketByLine = useMemo(() => {
    const m: Record<number, MarketPriceEstimate> = {};
    if (!marketPrices) return m;
    for (const it of marketPrices.items) m[it.tender_line_item_id] = it;
    return m;
  }, [marketPrices]);

  if (error) {
    return (
      <div className="space-y-6">
        <p className="text-sm text-destructive">{error}</p>
      </div>
    );
  }

  if (!tender) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const hasSplit = tender.bids.some((b) =>
    b.line_items.some(
      (bl) => bl.unit_price_labor !== null || bl.unit_price_material !== null,
    ),
  );
  const showSplit = viewMode === "detailed" && hasSplit;
  const colsPerBid = showSplit ? 3 : 1;

  return (
    <div className="space-y-6">
      {/* ----- Header ----- */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectId}/tenders`)}
          >
            <ArrowLeft className="mr-1 h-4 w-4" /> Back
          </Button>
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold">
              {tender.title}
              {tender.awarded_bid_id ? (
                <Trophy className="h-5 w-5 text-amber-500" />
              ) : null}
            </h1>
            <p className="text-sm text-muted-foreground">
              {tender.object_name ? `${tender.object_name} · ` : ""}
              {tender.currency} · {tender.bids.length} bid
              {tender.bids.length === 1 ? "" : "s"} ·{" "}
              {tender.line_items.length} line item
              {tender.line_items.length === 1 ? "" : "s"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm,.pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleBidFile(f);
            }}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileRef.current?.click()}
            disabled={extracting || tender.line_items.length === 0}
            title={
              tender.line_items.length === 0
                ? "Add line items first"
                : "Upload one company's quote"
            }
          >
            {extracting ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-1 h-4 w-4" />
            )}
            Add Bid (File)
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={startManualBid}
            disabled={tender.line_items.length === 0}
          >
            <Plus className="mr-1 h-4 w-4" /> Add Bid (Manual)
          </Button>
          <Link
            href={`/projects/${projectId}/tenders/${tenderId}/ai-analysis`}
          >
            <Button>
              <Sparkles className="mr-1 h-4 w-4" /> AI Analizi
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDeleteTender}
            title="Delete tender"
          >
            <Trash2 className="h-4 w-4 text-rose-500" />
          </Button>
        </div>
      </div>

      {/* ----- Bidder cards row ----- */}
      {tender.bids.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {tender.bids.map((b) => {
            const total = parseFloat(b.total_amount);
            const isCheap =
              bidExtremes.min > 0 && total === bidExtremes.min && total > 0;
            const isExp =
              bidExtremes.max > 0 && total === bidExtremes.max && total > 0;
            const variance = bidExtremes.min > 0 && total > 0
              ? pct(total, bidExtremes.min)
              : 0;
            return (
              <Card
                key={b.id}
                className={
                  "relative overflow-hidden " +
                  (b.id === tender.awarded_bid_id
                    ? "border-amber-400 ring-1 ring-amber-300"
                    : isCheap
                    ? "border-emerald-300"
                    : isExp
                    ? "border-rose-200"
                    : "")
                }
              >
                {isCheap ? (
                  <div className="absolute right-0 top-0 rounded-bl bg-emerald-500 px-2 py-0.5 text-[10px] font-medium text-white">
                    <TrendingDown className="mr-0.5 inline h-3 w-3" /> En düşük
                  </div>
                ) : isExp ? (
                  <div className="absolute right-0 top-0 rounded-bl bg-rose-500 px-2 py-0.5 text-[10px] font-medium text-white">
                    <TrendingUp className="mr-0.5 inline h-3 w-3" /> En yüksek
                  </div>
                ) : null}
                <CardContent className="space-y-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold" title={b.company_name}>
                        {b.company_name}
                        {b.id === tender.awarded_bid_id ? (
                          <Trophy className="ml-1 inline h-3 w-3 text-amber-500" />
                        ) : null}
                      </div>
                      {b.variant_label ? (
                        <Badge variant="outline" className="mt-1 text-[10px]">
                          {b.variant_label}
                        </Badge>
                      ) : null}
                    </div>
                    <button
                      onClick={() => handleDeleteBid(b.id)}
                      className="text-muted-foreground transition hover:text-rose-500"
                      title="Delete bid"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                  <div>
                    <div className="text-xl font-bold">
                      {fmtCurrency(b.total_amount, tender.currency)}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      net{" "}
                      {fmtCurrency(b.total_without_vat, tender.currency)} · НДС{" "}
                      {parseFloat(b.vat_rate || "20")}%
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-1 text-[11px]">
                    {!isCheap && variance > 0 ? (
                      <Badge variant="outline" className="border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-300">
                        +{variance.toFixed(1)}% vs cheapest
                      </Badge>
                    ) : null}
                    {b.delivery_days != null ? (
                      <Badge variant="outline">
                        {b.delivery_days} gün teslim
                      </Badge>
                    ) : null}
                  </div>
                  <div className="pt-1">
                    <Button
                      size="sm"
                      variant={
                        b.id === tender.awarded_bid_id ? "default" : "outline"
                      }
                      className="w-full"
                      disabled={awarding === b.id}
                      onClick={() => handleAward(b.id)}
                    >
                      {awarding === b.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : b.id === tender.awarded_bid_id ? (
                        <>
                          <Trophy className="mr-1 h-3 w-3" />
                          Awarded
                        </>
                      ) : (
                        "Award this bid"
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : null}

      {/* ----- View controls ----- */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex rounded-md border bg-card p-1 text-xs">
          <button
            onClick={() => setViewMode("simple")}
            className={
              "rounded px-3 py-1 transition " +
              (viewMode === "simple"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted")
            }
          >
            Sade
          </button>
          <button
            onClick={() => setViewMode("detailed")}
            className={
              "rounded px-3 py-1 transition " +
              (viewMode === "detailed"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted")
            }
            disabled={!hasSplit}
            title={hasSplit ? "" : "No labor/material split available"}
          >
            Detaylı
          </button>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            const next = !showMarketBox;
            setShowMarketBox(next);
            if (next) loadMarket();
          }}
        >
          <HelpCircle className="mr-1 h-4 w-4" />
          {showMarketBox ? "Hide market prices" : "Show market prices"}
        </Button>
      </div>

      {/* ----- Market price help-box ----- */}
      {showMarketBox ? (
        <MarketPriceBox
          loading={marketLoading}
          data={marketPrices}
          lineItems={tender.line_items}
        />
      ) : null}

      {/* ----- Comparison grid ----- */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="flex items-center gap-2 text-base">
            <Layers className="h-4 w-4 text-muted-foreground" />
            Karşılaştırma Tablosu
          </CardTitle>
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className="inline-block h-2 w-3 rounded bg-emerald-200" />
            En ucuz
            <span className="ml-2 inline-block h-2 w-3 rounded bg-amber-200" />
            Orta
            <span className="ml-2 inline-block h-2 w-3 rounded bg-rose-200" />
            En pahalı
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {tender.line_items.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">
              No line items yet.
            </p>
          ) : (
            <div className="relative">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-card">
                  <tr className="border-b text-left">
                    <th className="sticky left-0 z-20 w-12 bg-card p-2 text-xs">
                      #
                    </th>
                    <th className="sticky left-12 z-20 min-w-[260px] bg-card p-2 text-xs">
                      Description
                    </th>
                    <th className="w-16 p-2 text-xs">Unit</th>
                    <th className="w-24 p-2 text-right text-xs">Qty</th>
                    {tender.bids.map((b) => (
                      <th
                        key={b.id}
                        colSpan={colsPerBid}
                        className="border-l p-2 text-center text-xs"
                      >
                        <div className="truncate font-medium" title={b.company_name}>
                          {b.company_name}
                          {b.variant_label ? (
                            <span className="ml-1 text-[10px] text-muted-foreground">
                              · {b.variant_label}
                            </span>
                          ) : null}
                        </div>
                      </th>
                    ))}
                  </tr>
                  {showSplit ? (
                    <tr className="border-b text-[10px] text-muted-foreground">
                      <th
                        colSpan={4}
                        className="sticky left-0 bg-card"
                      ></th>
                      {tender.bids.map((b) => (
                        <>
                          <th
                            key={`${b.id}-lab`}
                            className="border-l p-1 text-right"
                          >
                            İşçilik
                          </th>
                          <th key={`${b.id}-mat`} className="p-1 text-right">
                            Malzeme
                          </th>
                          <th
                            key={`${b.id}-tot`}
                            className="p-1 text-right font-semibold"
                          >
                            Toplam
                          </th>
                        </>
                      ))}
                    </tr>
                  ) : null}
                </thead>
                <tbody>
                  {visibleNodes.map((node) => {
                    const li = node.line;
                    const ext = lineExtremes[li.id];
                    const isPackage = li.line_type === "package";
                    const hasChildren = node.children.length > 0;
                    const isCollapsed = collapsed.has(li.id);
                    const rowBg = isPackage
                      ? "bg-slate-50/80 font-medium dark:bg-slate-900/40"
                      : "";
                    return (
                      <tr
                        key={li.id}
                        className={"border-b group " + rowBg}
                      >
                        <td
                          className={
                            "sticky left-0 z-10 p-2 text-xs text-muted-foreground " +
                            (rowBg || "bg-card")
                          }
                        >
                          {li.display_label || li.order_num}
                        </td>
                        <td
                          className={
                            "sticky left-12 z-10 p-2 text-xs " +
                            (rowBg || "bg-card")
                          }
                        >
                          <div
                            className="flex items-center gap-1"
                            style={{ paddingLeft: `${node.depth * 14}px` }}
                          >
                            {hasChildren ? (
                              <button
                                onClick={() => toggleCollapse(li.id)}
                                className="text-muted-foreground transition hover:text-foreground"
                                aria-label={isCollapsed ? "Expand" : "Collapse"}
                              >
                                {isCollapsed ? (
                                  <ChevronRight className="h-3 w-3" />
                                ) : (
                                  <ChevronDown className="h-3 w-3" />
                                )}
                              </button>
                            ) : (
                              <span className="inline-block w-3" />
                            )}
                            <span className={isPackage ? "font-medium" : ""}>
                              {li.description}
                            </span>
                            {li.line_type === "work" ? (
                              <Badge
                                variant="outline"
                                className="ml-1 border-blue-200 bg-blue-50 px-1 py-0 text-[9px] text-blue-700 dark:bg-blue-950/30 dark:text-blue-300"
                              >
                                Работы
                              </Badge>
                            ) : null}
                            {li.line_type === "material" ? (
                              <Badge
                                variant="outline"
                                className="ml-1 border-purple-200 bg-purple-50 px-1 py-0 text-[9px] text-purple-700 dark:bg-purple-950/30 dark:text-purple-300"
                              >
                                Материал
                              </Badge>
                            ) : null}
                          </div>
                        </td>
                        <td className="p-2 text-xs">{li.unit ?? "—"}</td>
                        <td className="p-2 text-right text-xs">
                          {fmtNum(li.quantity)}
                        </td>
                        {tender.bids.map((b) => {
                          const cell = cellLookup[b.id]?.[li.id];
                          if (!cell) {
                            return (
                              <td
                                key={`empty-${b.id}-${li.id}`}
                                colSpan={colsPerBid}
                                className="border-l p-2 text-center text-xs text-muted-foreground"
                              >
                                —
                              </td>
                            );
                          }
                          if (cell.price_type !== "fixed") {
                            return (
                              <td
                                key={`txt-${b.id}-${li.id}`}
                                colSpan={colsPerBid}
                                className="border-l p-2 text-center text-[10px] italic text-amber-600 dark:text-amber-400"
                              >
                                {priceTypeBadge(cell.price_type, cell.raw_text_price)}
                              </td>
                            );
                          }
                          const total = parseFloat(cell.unit_price_total);
                          const tone =
                            ext && total > 0
                              ? cellTone(total, ext.min, ext.max)
                              : "";
                          if (showSplit) {
                            return (
                              <>
                                <td
                                  key={`lab-${b.id}-${li.id}`}
                                  className="border-l p-2 text-right text-xs"
                                >
                                  {cell.unit_price_labor
                                    ? fmtNum(cell.unit_price_labor)
                                    : "—"}
                                </td>
                                <td
                                  key={`mat-${b.id}-${li.id}`}
                                  className="p-2 text-right text-xs"
                                >
                                  {cell.unit_price_material
                                    ? fmtNum(cell.unit_price_material)
                                    : "—"}
                                </td>
                                <td
                                  key={`tot-${b.id}-${li.id}`}
                                  className={
                                    "p-2 text-right text-xs font-medium " + tone
                                  }
                                >
                                  {fmtNum(cell.unit_price_total)}
                                </td>
                              </>
                            );
                          }
                          return (
                            <td
                              key={`up-${b.id}-${li.id}`}
                              className={
                                "border-l p-2 text-right text-xs " + tone
                              }
                            >
                              {fmtNum(cell.unit_price_total)}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                  {/* Totals row */}
                  <tr className="border-t-2 bg-muted/40 font-semibold">
                    <td className="sticky left-0 z-10 bg-muted/40 p-2"></td>
                    <td className="sticky left-12 z-10 bg-muted/40 p-2 text-sm">
                      TOPLAM
                    </td>
                    <td className="p-2"></td>
                    <td className="p-2"></td>
                    {tender.bids.map((b) => {
                      const total = parseFloat(b.total_amount);
                      const cheap =
                        bidExtremes.min > 0 &&
                        total === bidExtremes.min &&
                        total > 0;
                      const exp =
                        bidExtremes.max > 0 &&
                        total === bidExtremes.max &&
                        total > 0;
                      const tone = cheap
                        ? "bg-emerald-100 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200"
                        : exp
                        ? "bg-rose-100 dark:bg-rose-950/40 text-rose-800 dark:text-rose-200"
                        : "";
                      if (showSplit) {
                        return (
                          <>
                            <td
                              key={`tot-lab-${b.id}`}
                              className="border-l p-2 text-right text-xs"
                            >
                              {fmtCurrency(b.total_labor, tender.currency)}
                            </td>
                            <td
                              key={`tot-mat-${b.id}`}
                              className="p-2 text-right text-xs"
                            >
                              {fmtCurrency(b.total_material, tender.currency)}
                            </td>
                            <td
                              key={`tot-amt-${b.id}`}
                              className={"p-2 text-right text-sm " + tone}
                            >
                              {fmtCurrency(b.total_amount, tender.currency)}
                            </td>
                          </>
                        );
                      }
                      return (
                        <td
                          key={`tot-amt-${b.id}`}
                          className={
                            "border-l p-2 text-right text-sm " + tone
                          }
                        >
                          {fmtCurrency(b.total_amount, tender.currency)}
                        </td>
                      );
                    })}
                  </tr>
                  {/* Net (no VAT) row */}
                  <tr className="border-b bg-muted/20 text-xs text-muted-foreground">
                    <td className="sticky left-0 z-10 bg-muted/20 p-2"></td>
                    <td
                      className="sticky left-12 z-10 bg-muted/20 p-2"
                      colSpan={3}
                    >
                      KDV hariç (без НДС)
                    </td>
                    {tender.bids.map((b) => (
                      <td
                        key={`net-${b.id}`}
                        colSpan={colsPerBid}
                        className="border-l p-2 text-right"
                      >
                        {fmtCurrency(b.total_without_vat, tender.currency)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ----- Bidder commentary ----- */}
      {tender.bids.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bidder commentary</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {tender.bids.map((b) => (
              <div key={b.id} className="rounded border bg-card p-3 text-sm">
                <div className="mb-1 flex items-center gap-1 font-medium">
                  {b.company_name}
                  {b.variant_label ? (
                    <Badge variant="outline" className="text-[10px]">
                      {b.variant_label}
                    </Badge>
                  ) : null}
                </div>
                {b.contact_name ? (
                  <div className="text-xs text-muted-foreground">
                    Contact: {b.contact_name}
                    {b.contact_phone ? ` · ${b.contact_phone}` : ""}
                  </div>
                ) : null}
                {b.included_in_price ? (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-muted-foreground">
                      Included
                    </div>
                    <p className="text-xs">{b.included_in_price}</p>
                  </div>
                ) : null}
                {b.not_included_in_price ? (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-muted-foreground">
                      Not included
                    </div>
                    <p className="text-xs">{b.not_included_in_price}</p>
                  </div>
                ) : null}
                {b.notes ? (
                  <div className="mt-2 text-xs text-muted-foreground">{b.notes}</div>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {/* ----- Draft bid modal ----- */}
      {draft && tender ? (
        <DraftBidModal
          draft={draft}
          tender={tender}
          onChange={setDraft}
          onCancel={() => setDraft(null)}
          onSave={saveDraftBid}
          saving={savingBid}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Market price help-box
// ---------------------------------------------------------------------------

function MarketPriceBox({
  loading,
  data,
  lineItems,
}: {
  loading: boolean;
  data: TenderMarketPrices | null;
  lineItems: TenderLineItem[];
}) {
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Info className="h-4 w-4 text-blue-500" />
            Market price band (Level 1)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-3/4" />
        </CardContent>
      </Card>
    );
  }
  if (!data) {
    return (
      <Card>
        <CardContent className="p-4 text-sm text-muted-foreground">
          No market price data available.
        </CardContent>
      </Card>
    );
  }
  const byId = new Map(data.items.map((it) => [it.tender_line_item_id, it]));
  return (
    <Card className="border-blue-200 bg-blue-50/40 dark:bg-blue-950/20">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Info className="h-4 w-4 text-blue-500" />
          Market price band (Level 1)
        </CardTitle>
        <p className="pt-1 text-[11px] text-muted-foreground">
          {data.disclaimer}
        </p>
      </CardHeader>
      <CardContent>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left text-[10px] text-muted-foreground">
              <th className="p-1.5">Item</th>
              <th className="p-1.5">Unit</th>
              <th className="p-1.5 text-right">Min</th>
              <th className="p-1.5 text-right">Typical</th>
              <th className="p-1.5 text-right">Max</th>
              <th className="p-1.5">Confidence</th>
              <th className="p-1.5">Driver</th>
            </tr>
          </thead>
          <tbody>
            {lineItems.map((li) => {
              const m = byId.get(li.id);
              return (
                <tr key={li.id} className="border-b last:border-b-0">
                  <td className="p-1.5">{li.description}</td>
                  <td className="p-1.5 text-muted-foreground">{li.unit ?? "—"}</td>
                  <td className="p-1.5 text-right">
                    {m?.min ? fmtNum(m.min) : "—"}
                  </td>
                  <td className="p-1.5 text-right font-medium">
                    {m?.typical ? fmtNum(m.typical) : "—"}
                  </td>
                  <td className="p-1.5 text-right">
                    {m?.max ? fmtNum(m.max) : "—"}
                  </td>
                  <td className="p-1.5">
                    {m ? (
                      <Badge
                        variant="outline"
                        className={
                          m.confidence === "HIGH"
                            ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                            : m.confidence === "MEDIUM"
                            ? "border-amber-300 bg-amber-50 text-amber-700"
                            : "border-slate-300 bg-slate-50 text-slate-700"
                        }
                      >
                        {m.confidence}
                      </Badge>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-1.5 text-muted-foreground">
                    {m?.note ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Draft bid modal (with variant + VAT + text-price support)
// ---------------------------------------------------------------------------

function DraftBidModal({
  draft,
  tender,
  onChange,
  onCancel,
  onSave,
  saving,
}: {
  draft: ExtractedBid;
  tender: Tender;
  onChange: (d: ExtractedBid) => void;
  onCancel: () => void;
  onSave: () => void;
  saving: boolean;
}) {
  const linesByOrder = new Map(draft.lines.map((l) => [l.order_num, l]));
  const fullRows = tender.line_items.map((li) => {
    const existing = linesByOrder.get(li.order_num);
    return {
      tenderLine: li,
      bid: existing ?? {
        order_num: li.order_num,
        unit_price_labor: null,
        unit_price_material: null,
        unit_price_total: "0",
        price_type: "fixed" as const,
        raw_text_price: null,
      },
    };
  });

  function setBidField<K extends keyof ExtractedBid>(key: K, val: ExtractedBid[K]) {
    onChange({ ...draft, [key]: val });
  }

  function setLine(
    orderNum: number,
    patch: Partial<{
      unit_price_labor: string | null;
      unit_price_material: string | null;
      unit_price_total: string;
      price_type: "fixed" | "negotiable" | "not_included" | "on_request";
      raw_text_price: string | null;
    }>,
  ) {
    const existing = linesByOrder.get(orderNum) ?? {
      order_num: orderNum,
      unit_price_labor: null,
      unit_price_material: null,
      unit_price_total: "0",
      price_type: "fixed" as const,
      raw_text_price: null,
    };
    const merged = { ...existing, ...patch };
    if (merged.unit_price_labor != null && merged.unit_price_material != null) {
      const lab = parseFloat(String(merged.unit_price_labor)) || 0;
      const mat = parseFloat(String(merged.unit_price_material)) || 0;
      merged.unit_price_total = String(lab + mat);
    }
    const others = draft.lines.filter((l) => l.order_num !== orderNum);
    onChange({
      ...draft,
      lines: [...others, merged].sort((a, b) => a.order_num - b.order_num),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-lg bg-background shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-background p-4">
          <div>
            <h2 className="text-lg font-semibold">Review bid</h2>
            <p className="text-xs text-muted-foreground">
              Fix any AI mistakes before saving
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          {/* Company + variant + VAT */}
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <Label>Company *</Label>
              <Input
                value={draft.company_name}
                onChange={(e) => setBidField("company_name", e.target.value)}
                placeholder="ООО АгроЦентрик"
              />
            </div>
            <div>
              <Label>Variant (if any)</Label>
              <Input
                value={draft.variant_label ?? ""}
                onChange={(e) =>
                  setBidField("variant_label", e.target.value || null)
                }
                placeholder="Dairy Plus / Sistem A"
              />
            </div>
            <div>
              <Label>VAT %</Label>
              <Input
                type="number"
                step="0.1"
                value={draft.vat_rate ?? "20"}
                onChange={(e) => setBidField("vat_rate", e.target.value)}
              />
            </div>
            <div>
              <Label>Contact</Label>
              <Input
                value={draft.contact_name ?? ""}
                onChange={(e) =>
                  setBidField("contact_name", e.target.value || null)
                }
              />
            </div>
            <div>
              <Label>Phone</Label>
              <Input
                value={draft.contact_phone ?? ""}
                onChange={(e) =>
                  setBidField("contact_phone", e.target.value || null)
                }
              />
            </div>
            <div>
              <Label>Delivery (days)</Label>
              <Input
                type="number"
                value={draft.delivery_days ?? ""}
                onChange={(e) =>
                  setBidField(
                    "delivery_days",
                    e.target.value ? parseInt(e.target.value, 10) : null,
                  )
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            <div>
              <Label>Included in price</Label>
              <textarea
                className="w-full resize-none rounded-md border bg-card p-2 text-sm"
                rows={2}
                value={draft.included_in_price ?? ""}
                onChange={(e) =>
                  setBidField("included_in_price", e.target.value || null)
                }
              />
            </div>
            <div>
              <Label>NOT included</Label>
              <textarea
                className="w-full resize-none rounded-md border bg-card p-2 text-sm"
                rows={2}
                value={draft.not_included_in_price ?? ""}
                onChange={(e) =>
                  setBidField("not_included_in_price", e.target.value || null)
                }
              />
            </div>
          </div>

          {/* Per-line prices */}
          <div className="rounded border">
            <table className="w-full text-xs">
              <thead className="bg-muted/40">
                <tr>
                  <th className="p-2 text-left">#</th>
                  <th className="p-2 text-left">Description</th>
                  <th className="p-2 text-left">Unit</th>
                  <th className="p-2 text-right">Qty</th>
                  <th className="p-2 text-right">İşçilik</th>
                  <th className="p-2 text-right">Malzeme</th>
                  <th className="p-2 text-right">Toplam</th>
                  <th className="p-2">Type</th>
                </tr>
              </thead>
              <tbody>
                {fullRows.map(({ tenderLine, bid }) => {
                  const pt = bid.price_type ?? "fixed";
                  const isText = pt !== "fixed";
                  return (
                    <tr key={tenderLine.id} className="border-t">
                      <td className="p-2">
                        {tenderLine.display_label || tenderLine.order_num}
                      </td>
                      <td className="p-2">{tenderLine.description}</td>
                      <td className="p-2 text-muted-foreground">
                        {tenderLine.unit ?? "—"}
                      </td>
                      <td className="p-2 text-right">
                        {fmtNum(tenderLine.quantity)}
                      </td>
                      <td className="p-2">
                        <Input
                          type="number"
                          step="any"
                          className="h-8 text-right"
                          disabled={isText}
                          value={bid.unit_price_labor ?? ""}
                          onChange={(e) =>
                            setLine(tenderLine.order_num, {
                              unit_price_labor: e.target.value || null,
                            })
                          }
                        />
                      </td>
                      <td className="p-2">
                        <Input
                          type="number"
                          step="any"
                          className="h-8 text-right"
                          disabled={isText}
                          value={bid.unit_price_material ?? ""}
                          onChange={(e) =>
                            setLine(tenderLine.order_num, {
                              unit_price_material: e.target.value || null,
                            })
                          }
                        />
                      </td>
                      <td className="p-2">
                        {isText ? (
                          <Input
                            className="h-8"
                            placeholder="Договорная"
                            value={bid.raw_text_price ?? ""}
                            onChange={(e) =>
                              setLine(tenderLine.order_num, {
                                raw_text_price: e.target.value || null,
                              })
                            }
                          />
                        ) : (
                          <Input
                            type="number"
                            step="any"
                            className="h-8 text-right"
                            value={bid.unit_price_total ?? "0"}
                            onChange={(e) =>
                              setLine(tenderLine.order_num, {
                                unit_price_total: e.target.value || "0",
                              })
                            }
                          />
                        )}
                      </td>
                      <td className="p-2">
                        <select
                          className="h-8 rounded border bg-card px-1 text-[11px]"
                          value={pt}
                          onChange={(e) =>
                            setLine(tenderLine.order_num, {
                              price_type: e.target.value as
                                | "fixed"
                                | "negotiable"
                                | "not_included"
                                | "on_request",
                              ...(e.target.value !== "fixed"
                                ? {
                                    unit_price_labor: null,
                                    unit_price_material: null,
                                    unit_price_total: "0",
                                  }
                                : {}),
                            })
                          }
                        >
                          <option value="fixed">numeric</option>
                          <option value="negotiable">Договорная</option>
                          <option value="not_included">не включена</option>
                          <option value="on_request">по запросу</option>
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="sticky bottom-0 flex items-center justify-end gap-2 border-t bg-background p-3">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              "Save bid"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
