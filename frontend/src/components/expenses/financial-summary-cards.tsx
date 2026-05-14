"use client";

import { useEffect, useState } from "react";
import { Building2, AlertCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api-client";
import type { FinancialSummary } from "@/types/financial-summary";

interface Props {
  projectId: number;
  /** Bump this number to force a re-fetch (e.g. after Excel import completes). */
  refreshKey?: number;
}

const COMPANIES: Array<{ label: string; tone: string; accent: string }> = [
  {
    label: "Monotek",
    tone: "border-indigo-200 bg-indigo-50/40 dark:border-indigo-900 dark:bg-indigo-950/20",
    accent: "text-[#143C73]",
  },
  {
    label: "Monart",
    tone: "border-sky-200 bg-sky-50/40 dark:border-sky-900 dark:bg-sky-950/20",
    accent: "text-[#1FA3DA]",
  },
];

function fmt(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  return n.toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("tr-TR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function amountClass(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n) || n === 0) return "text-muted-foreground";
  return n > 0
    ? "text-emerald-600 dark:text-emerald-400"
    : "text-rose-600 dark:text-rose-400";
}

export function FinancialSummaryCards({ projectId, refreshKey = 0 }: Props) {
  const [summaries, setSummaries] = useState<FinancialSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.financialSummary.list(projectId);
      setSummaries(data);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yüklenemedi");
    }
  }

  useEffect(() => {
    if (projectId > 0) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, refreshKey]);

  // Şirket bazlı eşle
  const byCompany: Record<string, FinancialSummary | undefined> = {};
  if (summaries) {
    for (const s of summaries) byCompany[s.company_label] = s;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-6 text-sm text-rose-600">
          <AlertCircle className="h-4 w-4" /> {error}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="h-4 w-4 text-primary" />
          Finansal Özet
        </CardTitle>
      </CardHeader>
      <CardContent>
        {summaries === null ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Skeleton className="h-80 w-full" />
            <Skeleton className="h-80 w-full" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {COMPANIES.map((c) => {
              const s = byCompany[c.label];
              return (
                <div
                  key={c.label}
                  className={`rounded-lg border ${c.tone} p-4`}
                >
                  {/* Card header */}
                  <div className="mb-3">
                    <div className={`text-base font-bold tracking-tight ${c.accent}`}>
                      {c.label.toUpperCase()}STROY
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {s ? formatDate(s.as_of_date) : "OZET sayfası henüz yüklenmemiş"}
                    </div>
                  </div>

                  {s ? (
                    <table className="w-full text-sm">
                      <tbody>
                        <SummaryRow label="ISVEREN TAHSILATLARI"   value={s.isveren_tahsilatlari} />
                        <SummaryRow label="FIRMA ODEMELERI"        value={s.firma_odemeleri} />
                        <SummaryRow label="UCRET GIDERLERI"        value={s.ucret_giderleri} />
                        <SummaryRow label="VERGI ODEMELERI"        value={s.vergi_odemeleri} bold />
                        <SummaryRow label="Gelir Vergisi"          value={s.gelir_vergisi} indent />
                        <SummaryRow label="KDV"                    value={s.kdv} indent />
                        <SummaryRow label="FAIZ GELIRLERI"         value={s.faiz_gelirleri} />
                        <SummaryRow label="BANKA GIDERLERI"        value={s.banka_giderleri} />
                        <SummaryRow label="DIGER GELIR-GIDERLER"   value={s.diger_gelir_giderler} />
                        <tr className="border-t-2 border-foreground/20">
                          <td className="py-2 text-sm font-bold">TOPLAM</td>
                          <td className={`py-2 text-right text-base font-bold tabular-nums ${amountClass(s.toplam)}`}>
                            {fmt(s.toplam)} ₽
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  ) : (
                    <div className="py-8 text-center text-sm text-muted-foreground">
                      {c.label} için OZET verisi henüz yok.
                      <div className="mt-2 text-xs">
                        Yukarıdaki <strong>Excel Yükle</strong> butonundan{" "}
                        <code className="rounded bg-muted px-1 py-0.5">
                          Harcama Takip-...-{c.label}.xlsx
                        </code>{" "}
                        dosyasını yükleyince otomatik dolar.
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SummaryRow({
  label,
  value,
  indent = false,
  bold = false,
}: {
  label: string;
  value: string | number;
  indent?: boolean;
  bold?: boolean;
}) {
  return (
    <tr className="border-b border-foreground/5">
      <td
        className={
          (indent ? "pl-5 text-xs italic " : "text-xs ") +
          (bold ? "py-1.5 font-semibold" : "py-1.5") +
          " text-foreground/80"
        }
      >
        {label}
      </td>
      <td
        className={
          "py-1.5 text-right text-xs tabular-nums " +
          (bold ? "font-semibold " : "") +
          amountClass(value)
        }
      >
        {fmt(value)} ₽
      </td>
    </tr>
  );
}
