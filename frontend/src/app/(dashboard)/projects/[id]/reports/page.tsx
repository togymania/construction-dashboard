"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Sparkles,
  RefreshCw,
  Bot,
  FileText,
  AlertTriangle,
  Wallet,
  HardHat,
  Users,
  CalendarRange,
  Lightbulb,
  Printer,
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
import { Separator } from "@/components/ui/separator";
import { api, ApiError } from "@/lib/api-client";
import { useProject } from "@/components/providers/project-provider";
import { useT } from "@/lib/i18n/provider";
import type { ProjectExecutiveReport } from "@/types/project";

export default function ProjectReportsPage() {
  const params = useParams<{ id: string }>();
  const projectId = parseInt(params.id, 10);
  const { project } = useProject();
  const { t } = useT();

  const [report, setReport] = useState<ProjectExecutiveReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(force = false) {
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await api.projects.executiveReport(projectId, force);
      setReport(data);
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : t("reports.errLoad");
      setError(msg);
      if (force) toast.error(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (projectId > 0) load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  function handlePrint() {
    if (typeof window !== "undefined") window.print();
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-72 w-full" />
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          {error || t("reports.noData")}
          <div className="mt-3">
            <Button size="sm" variant="outline" onClick={() => load(true)}>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              {t("reports.retry")}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const sourceLabel = report.source === "llm" ? t("reports.aiGenerated") : t("reports.ruleBased");

  return (
    <div className="space-y-6">
      {/* Cover card */}
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-cyan-500/5">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                {t("reports.execLabel")}
              </p>
              <CardTitle className="text-2xl flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                {report.project_name}
              </CardTitle>
              <p className="text-sm font-medium text-foreground/90 mt-2">
                {report.headline}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0 print:hidden">
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
                  className={`h-3.5 w-3.5 mr-1.5 ${
                    refreshing ? "animate-spin" : ""
                  }`}
                />
                {t("reports.refresh")}
              </Button>
              <Button size="sm" variant="default" onClick={handlePrint}>
                <Printer className="h-3.5 w-3.5 mr-1.5" />
                {t("reports.print")}
              </Button>
            </div>
          </div>
        </CardHeader>
        {project && (
          <CardContent>
            <div className="grid gap-3 grid-cols-2 md:grid-cols-4 text-sm">
              <Meta label={t("reports.mStatus")} value={project.status} />
              <Meta label={t("reports.mHealth")} value={project.health} />
              <Meta
                label={t("reports.mProgress")}
                value={`%${parseFloat(project.progress_pct).toFixed(0)}`}
              />
              <Meta label={t("reports.mLocation")} value={project.location} />
            </div>
          </CardContent>
        )}
      </Card>

      {/* Executive summary */}
      <ReportSection
        icon={<FileText className="h-4 w-4 text-primary" />}
        title={t("reports.execSummary")}
        body={report.sections.executive_summary}
      />

      {/* Two-column: Financial + Risks */}
      <div className="grid gap-4 md:grid-cols-2">
        <ReportSection
          icon={<Wallet className="h-4 w-4 text-emerald-500" />}
          title={t("reports.financialStatus")}
          body={report.sections.financial_status}
        />
        <ReportSection
          icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
          title={t("reports.criticalRisks")}
          body={report.sections.critical_risks}
        />
      </div>

      {/* Two-column: Subcontractor + Workforce */}
      <div className="grid gap-4 md:grid-cols-2">
        <ReportSection
          icon={<HardHat className="h-4 w-4 text-blue-500" />}
          title={t("reports.subPerf")}
          body={report.sections.subcontractor_performance}
        />
        <ReportSection
          icon={<Users className="h-4 w-4 text-cyan-500" />}
          title={t("reports.workforceHealth")}
          body={report.sections.workforce_health}
        />
      </div>

      {/* Forward-looking */}
      <ReportSection
        icon={<CalendarRange className="h-4 w-4 text-indigo-500" />}
        title={t("reports.next30Days")}
        body={report.sections.next_30_days}
      />

      {/* Recommended actions */}
      <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-primary" />
            {t("reports.recActions")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {report.recommended_actions.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              {t("reports.noRecs")}
            </p>
          ) : (
            <ul className="space-y-2">
              {report.recommended_actions.map((a, i) => (
                <li key={i} className="text-sm flex items-start gap-3">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary mt-2 shrink-0" />
                  <span className="leading-relaxed">{a}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Separator />

      <p className="text-[10px] text-muted-foreground text-right">
        {t("reports.generatedAt")} {new Date(report.generated_at).toLocaleString()} ·{" "}
        {sourceLabel}
      </p>
    </div>
  );
}

// ---------- Helpers ----------

function ReportSection({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
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
        <p className="text-sm text-foreground/85 leading-relaxed whitespace-pre-line">
          {body}
        </p>
      </CardContent>
    </Card>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-sm font-medium mt-0.5 capitalize">
        {value.replace(/_/g, " ")}
      </p>
    </div>
  );
}
p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-sm font-medium mt-0.5 capitalize">
        {value.replace(/_/g, " ")}
      </p>
    </div>
  );
}
