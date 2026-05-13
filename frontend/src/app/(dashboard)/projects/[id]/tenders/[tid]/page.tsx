"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Sparkles,
  Trophy,
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
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api-client";
import { formatRubCompact } from "@/lib/formatters";
import type { Bid, BidLineItem, Tender } from "@/types/tender";

function hasAnySplit(t: Tender): boolean {
  return t.bids.some((b) =>
    b.line_items.some(
      (bl) =>
        bl.unit_price_labor !== null || bl.unit_price_material !== null,
    ),
  );
}

function fmtCurrency(value: string | number, currency: string): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  const compact = formatRubCompact(n);
  // formatRubCompact stamps "₽"; replace if user picked another currency
  if (currency && currency !== "RUB") {
    return compact.replace("₽", currency);
  }
  return compact;
}

export default function TenderDetailPage() {
  const params = useParams<{ id: string; tid: string }>();
  const projectId = parseInt(params.id, 10);
  const tenderId = parseInt(params.tid, 10);
  const router = useRouter();

  const [tender, setTender] = useState<Tender | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [awarding, setAwarding] = useState<number | null>(null);

  async function load() {
    try {
      const data = await api.tenders.get(tenderId);
      setTender(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load tender");
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

  const split = hasAnySplit(tender);
  // index bid_lines by tender_line_item_id for quick lookup
  const cellLookup: Record<number, Record<number, BidLineItem | undefined>> = {};
  for (const b of tender.bids) {
    cellLookup[b.id] = {};
    for (const bl of b.line_items) {
      cellLookup[b.id][bl.tender_line_item_id] = bl;
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
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
              {tender.object_name} · {tender.currency} · {tender.bids.length}{" "}
              bid{tender.bids.length === 1 ? "" : "s"}
            </p>
          </div>
        </div>
        <Link
          href={`/projects/${projectId}/tenders/${tenderId}/ai-analysis`}
        >
          <Button>
            <Sparkles className="mr-1 h-4 w-4" /> AI Analizi
          </Button>
        </Link>
      </div>

      {/* Comparison grid */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Comparison grid</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {tender.line_items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No line items yet.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="w-10 p-2 align-bottom text-xs">#</th>
                  <th className="min-w-[200px] p-2 align-bottom text-xs">
                    Description
                  </th>
                  <th className="w-16 p-2 align-bottom text-xs">Unit</th>
                  <th className="w-20 p-2 text-right align-bottom text-xs">
                    Qty
                  </th>
                  {tender.bids.map((b) => (
                    <th
                      key={b.id}
                      colSpan={split ? 3 : 2}
                      className="border-l p-2 text-center align-bottom text-xs"
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="truncate font-medium" title={b.company_name}>
                          {b.company_name}
                          {b.id === tender.awarded_bid_id ? (
                            <Trophy className="ml-1 inline h-3 w-3 text-amber-500" />
                          ) : null}
                        </span>
                        <button
                          onClick={() => handleDeleteBid(b.id)}
                          className="opacity-0 transition hover:text-rose-500 group-hover:opacity-100"
                          aria-label="Delete bid"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </th>
                  ))}
                </tr>
                {split ? (
                  <tr className="border-b text-[10px] text-muted-foreground">
                    <th colSpan={4}></th>
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
                        <th key={`${b.id}-tot`} className="p-1 text-right">
                          Toplam
                        </th>
                      </>
                    ))}
                  </tr>
                ) : (
                  <tr className="border-b text-[10px] text-muted-foreground">
                    <th colSpan={4}></th>
                    {tender.bids.map((b) => (
                      <>
                        <th
                          key={`${b.id}-up`}
                          className="border-l p-1 text-right"
                        >
                          Birim
                        </th>
                        <th key={`${b.id}-lt`} className="p-1 text-right">
                          Toplam
                        </th>
                      </>
                    ))}
                  </tr>
                )}
              </thead>
              <tbody>
                {tender.line_items.map((li, idx) => (
                  <tr key={li.id} className="border-b">
                    <td className="p-2 text-xs text-muted-foreground">
                      {idx + 1}
                    </td>
                    <td className="p-2">{li.description}</td>
                    <td className="p-2 text-xs">{li.unit ?? "—"}</td>
                    <td className="p-2 text-right">
                      {parseFloat(li.quantity).toLocaleString()}
                    </td>
                    {tender.bids.map((b) => {
                      const cell = cellLookup[b.id]?.[li.id];
                      if (!cell) {
                        return (
                          <td
                            key={b.id}
                            colSpan={split ? 3 : 2}
                            className="border-l p-2 text-center text-xs text-muted-foreground"
                          >
                            —
                          </td>
                        );
                      }
                      if (split) {
                        return (
                          <>
                            <td
                              key={`${b.id}-${li.id}-lab`}
                              className="border-l p-2 text-right text-xs"
                            >
                              {cell.unit_price_labor
                                ? parseFloat(cell.unit_price_labor).toLocaleString()
                                : "—"}
                            </td>
                            <td
                              key={`${b.id}-${li.id}-mat`}
                              className="p-2 text-right text-xs"
                            >
                              {cell.unit_price_material
                                ? parseFloat(cell.unit_price_material).toLocaleString()
                                : "—"}
                            </td>
                            <td
                              key={`${b.id}-${li.id}-tot`}
                              className="p-2 text-right text-xs font-medium"
                            >
                              {parseFloat(cell.line_total).toLocaleString()}
                            </td>
                          </>
                        );
                      }
                      return (
                        <>
                          <td
                            key={`${b.id}-${li.id}-up`}
                            className="border-l p-2 text-right text-xs"
                          >
                            {parseFloat(cell.unit_price_total).toLocaleString()}
                          </td>
                          <td
                            key={`${b.id}-${li.id}-lt`}
                            className="p-2 text-right text-xs font-medium"
                          >
                            {parseFloat(cell.line_total).toLocaleString()}
                          </td>
                        </>
                      );
                    })}
                  </tr>
                ))}
                {/* Totals row */}
                <tr className="border-t-2 bg-muted/30 font-semibold">
                  <td className="p-2"></td>
                  <td className="p-2">TOTAL</td>
                  <td className="p-2"></td>
                  <td className="p-2"></td>
                  {tender.bids.map((b) => {
                    if (split) {
                      return (
                        <>
                          <td
                            key={`${b.id}-tot-lab`}
                            className="border-l p-2 text-right text-xs"
                          >
                            {fmtCurrency(b.total_labor, tender.currency)}
                          </td>
                          <td
                            key={`${b.id}-tot-mat`}
                            className="p-2 text-right text-xs"
                          >
                            {fmtCurrency(b.total_material, tender.currency)}
                          </td>
                          <td
                            key={`${b.id}-tot-amt`}
                            className="p-2 text-right text-sm"
                          >
                            {fmtCurrency(b.total_amount, tender.currency)}
                          </td>
                        </>
                      );
                    }
                    return (
                      <>
                        <td
                          key={`${b.id}-tot-up`}
                          className="border-l p-2"
                        ></td>
                        <td
                          key={`${b.id}-tot-amt`}
                          className="p-2 text-right text-sm"
                        >
                          {fmtCurrency(b.total_amount, tender.currency)}
                        </td>
                      </>
                    );
                  })}
                </tr>
                {/* Delivery */}
                <tr>
                  <td className="p-2"></td>
                  <td colSpan={3} className="p-2 text-xs text-muted-foreground">
                    Delivery (days)
                  </td>
                  {tender.bids.map((b) => (
                    <td
                      key={`${b.id}-dd`}
                      colSpan={split ? 3 : 2}
                      className="border-l p-2 text-center text-xs"
                    >
                      {b.delivery_days ?? "—"}
                    </td>
                  ))}
                </tr>
                {/* Award row */}
                <tr>
                  <td colSpan={4}></td>
                  {tender.bids.map((b) => (
                    <td
                      key={`${b.id}-act`}
                      colSpan={split ? 3 : 2}
                      className="border-l p-2 text-center"
                    >
                      <Button
                        size="sm"
                        variant={
                          b.id === tender.awarded_bid_id ? "default" : "outline"
                        }
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
                          "Award"
                        )}
                      </Button>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Bid footers: included / not included / notes */}
      {tender.bids.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bidder commentary</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {tender.bids.map((b) => (
              <div key={b.id} className="rounded border bg-card p-3 text-sm">
                <div className="mb-1 font-medium">{b.company_name}</div>
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
    </div>
  );
}
