"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  RefreshCw,
  AlertTriangle,
  TrendingUp,
  Calendar,
  ShieldCheck,
  FileText,
  Wallet,
  CheckCircle2,
  Bot,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { api, ApiError } from "@/lib/api-client";
import type { SubcontractorProfileReport } from "@/types/subcontractor";
import { formatRubCompact } from "@/lib/formatters";

interface Props {
  subcontractorId: number;
}

/**
 * The "Firma Kartviziti" — a single executive view of a subcontractor.
 *
 * Aggregates contracts, payments and contract documents (extracted_data) into
 * a Claude-narrated profile. When no API key is configured, the backend falls
 * back to rule-based copy and `source` becomes "rule".
 */
export function SubcontractorProfileCard({ subcontractorId }: Props) {
  const [report, setReport] = useState<SubcontractorProfileReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(forceRefresh = false) {
    if (forceRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await api.subcontractors.profileReport(
        subcontractorId,
        forceRefresh
      );
      setReport(data);
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : "Failed to load profile report";
      setError(msg);
      if (forceRefresh) toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subcontractorId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          {error || "No profile data available."}
          <div className="mt-3">
            <Button size="sm" variant="outline" onClick={() => load(true)}>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const sourceLabel =
    report.source === "llm"
      ? "AI Generated"
      : report.source === "llm_mock"
      ? "AI (mock — awaiting API key)"
      : "Rule-based";

  const riskColor =
    report.risk_score === null
      ? "bg-muted text-muted-foreground"
      : report.risk_score >= 70
      ? "bg-rose-500/15 text-rose-600 dark:text-rose-400"
      : report.risk_score >= 40
      ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
      : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400";

  return (
    <div className="space-y-4">
      {/* Header card with source badge + refresh */}
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-cyan-500/5">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="text-lg flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                Firma Kartviziti
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Tüm kontratlar, ödemeler ve {report.documents_analyzed} adet
                yüklenmiş döküman birleştirilerek üretildi.
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Badge
                variant="outline"
                className="text-[10px] gap-1 bg-primary/10 border-primary/30"
              >
                <Bot className="h-3 w-3" />
                {sourceLabel}
              </Badge>
              <Button
                size="sm"
                variant="outline"
                onClick={() => load(true)}
                disabled={refreshing}
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`}
                />
                Yenile
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Top KPI strip */}
          <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
            <KpiTile
              icon={<Wallet className="h-3.5 w-3.5" />}
              label="Toplam Değer"
              value={formatRubCompact(report.total_contract_value)}
            />
            <KpiTile
              icon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
              label="Ödenen"
              value={formatRubCompact(report.total_paid)}
            />
            <KpiTile
              icon={<TrendingUp className="h-3.5 w-3.5 text-amber-500" />}
              label="Bekleyen"
              value={formatRubCompact(report.pending_amount)}
            />
            <KpiTile
              icon={<FileText className="h-3.5 w-3.5" />}
              label="Aktif / Bitmiş"
              value={`${report.active_contract_count} / ${report.completed_contract_count}`}
            />
            <KpiTile
              icon={<ShieldCheck className="h-3.5 w-3.5" />}
              label="Risk"
              value={
                report.risk_score === null ? "—" : `${report.risk_score}/100`
              }
              className={riskColor}
            />
          </div>
        </CardContent>
      </Card>

      {/* Narrative sections */}
      <div className="grid gap-4 md:grid-cols-2">
        <NarrativeCard
          icon={<FileText className="h-4 w-4" />}
          title={report.company_overview.heading}
          body={report.company_overview.body}
        />
        <NarrativeCard
          icon={<Wallet className="h-4 w-4" />}
          title={report.financial_summary.heading}
          body={report.financial_summary.body}
          extra={
            report.avg_payment_delay_days !== null && (
              <p className="text-[11px] text-muted-foreground mt-2">
                Ort. ödeme gecikmesi:{" "}
                <span className="font-medium text-foreground">
                  {report.avg_payment_delay_days.toFixed(1)} gün
                </span>
              </p>
            )
          }
        />
        <NarrativeCard
          icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
          title={report.risk_profile.heading}
          body={report.risk_profile.body}
          extra={
            report.aggregated_risk_flags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-3">
                {report.aggregated_risk_flags.slice(0, 6).map((f, i) => (
                  <Badge
                    key={i}
                    variant="outline"
                    className="text-[10px] border-amber-500/40 text-amber-700 dark:text-amber-400"
                  >
                    {f}
                  </Badge>
                ))}
              </div>
            )
          }
        />
        <NarrativeCard
          icon={<Calendar className="h-4 w-4 text-blue-500" />}
          title={report.payment_terms_summary.heading}
          body={report.payment_terms_summary.body}
        />
      </div>

      {/* Penalty patterns + Timeline + Recommendations */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Penalty patterns */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-rose-500" />
              Penalty Patterns
            </CardTitle>
          </CardHeader>
          <CardContent>
            {report.penalty_patterns.length === 0 ? (
              <p className="text-xs text-muted-foreground italic">
                No penalty clauses extracted yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {report.penalty_patterns.slice(0, 6).map((p, i) => (
                  <li
                    key={i}
                    className="rounded-md border border-rose-200/60 dark:border-rose-900/40 bg-rose-50/40 dark:bg-rose-950/20 p-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium truncate">
                        {p.trigger}
                      </span>
                      {p.typical_amount && (
                        <Badge
                          variant="outline"
                          className="text-[10px] font-mono shrink-0"
                        >
                          {p.typical_amount}
                        </Badge>
                      )}
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {p.penalty_type}
                      {p.occurrences > 1 ? ` · ${p.occurrences}× görüldü` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Key dates timeline */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Calendar className="h-3.5 w-3.5 text-blue-500" />
              Kritik Tarihler
            </CardTitle>
          </CardHeader>
          <CardContent>
            {report.key_dates_timeline.length === 0 ? (
              <p className="text-xs text-muted-foreground italic">
                No key dates extracted yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {report.key_dates_timeline.slice(0, 8).map((kd, i) => (
                  <li key={i} className="text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-blue-600 dark:text-blue-400 w-20 shrink-0">
                        {kd.date}
                      </span>
                      <span className="font-medium truncate">{kd.label}</span>
                    </div>
                    {kd.description && (
                      <p className="text-[10px] text-muted-foreground ml-22 mt-0.5 line-clamp-2">
                        {kd.description}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Recommendations */}
        <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              Tavsiye Edilen Aksiyonlar
            </CardTitle>
          </CardHeader>
          <CardContent>
            {report.recommendations.length === 0 ? (
              <p className="text-xs text-muted-foreground italic">
                No recommendations.
              </p>
            ) : (
              <ul className="space-y-2">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="text-xs flex items-start gap-2">
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                    <span className="leading-relaxed">{r}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {report.source === "llm_mock" && (
        <div className="rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900/40 dark:bg-amber-950/30 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
          <strong>Not:</strong> Profil özeti şu an mock veri ile üretildi.
          Gerçek Claude analizine geçmek için sunucuda{" "}
          <code className="font-mono">ANTHROPIC_API_KEY</code> tanımlanmalı.
        </div>
      )}

      <p className="text-[10px] text-muted-foreground text-right">
        Generated at {new Date(report.generated_at).toLocaleString()}
      </p>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function KpiTile({
  icon,
  label,
  value,
  className,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div
      className={`rounded-md border bg-card p-3 ${className || ""}`}
    >
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide flex items-center gap-1">
        {icon}
        {label}
      </p>
      <p className="text-base font-bold mt-1 truncate">{value}</p>
    </div>
  );
}

function NarrativeCard({
  icon,
  title,
  body,
  extra,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  extra?: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-foreground leading-relaxed">{body}</p>
        {extra}
      </CardContent>
    </Card>
  );
}
