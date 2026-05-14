"use client";

import { useEffect, useState } from "react";
import { TrendingUp, AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api-client";
import { formatRubCompact } from "@/lib/formatters";
import { useT } from "@/lib/i18n/provider";

interface EACBundle {
  bac: number;
  ac: number;
  ev: number;
  cpi: number;
  eac: number;
  vac: number;
  progress_pct: number;
  status: "OVER_BUDGET" | "ON_TRACK" | "UNDER_BUDGET" | "UNKNOWN";
}

function statusStyles(
  status: EACBundle["status"],
  t: (k: string) => string,
): {
  variant: "default" | "secondary" | "destructive" | "outline";
  className: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
} {
  switch (status) {
    case "OVER_BUDGET":
      return {
        variant: "destructive",
        className: "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900",
        label: t("eac.statusOverBudget"),
        icon: AlertTriangle,
      };
    case "UNDER_BUDGET":
      return {
        variant: "default",
        className: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900",
        label: t("eac.statusUnderBudget"),
        icon: CheckCircle2,
      };
    case "ON_TRACK":
      return {
        variant: "secondary",
        className: "border-blue-200 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900",
        label: t("eac.statusOnTrack"),
        icon: CheckCircle2,
      };
    default:
      return {
        variant: "outline",
        className: "",
        label: t("eac.statusUnknown"),
        icon: HelpCircle,
      };
  }
}

export function EACWidget({ projectId }: { projectId: number }) {
  const { t } = useT();
  const [data, setData] = useState<EACBundle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api.projects
      .eac(projectId)
      .then((d) => mounted && setData(d))
      .catch((e) =>
        mounted &&
        setError(e instanceof ApiError ? e.message : t("eac.errorLoad"))
      );
    return () => {
      mounted = false;
    };
  }, [projectId, t]);

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingUp className="h-4 w-4" />
            {t("eac.title")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingUp className="h-4 w-4" />
            {t("eac.title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </CardContent>
      </Card>
    );
  }

  const styles = statusStyles(data.status, t);
  const Icon = styles.icon;
  const variancePositive = data.vac >= 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingUp className="h-4 w-4" />
          EAC Forecast
        </CardTitle>
        <Badge variant="outline" className={styles.className}>
          <Icon className="mr-1 h-3 w-3" />
          {styles.label}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <Stat label={t("eac.bacLabel")} value={formatRubCompact(data.bac)} />
          <Stat label={t("eac.acLabel")} value={formatRubCompact(data.ac)} />
          <Stat
            label={t("eac.eacLabel")}
            value={formatRubCompact(data.eac)}
            highlight
          />
        </div>
        <div className="grid grid-cols-3 gap-3 text-xs">
          <SubStat label={t("eac.progressLabel")} value={`${data.progress_pct.toFixed(0)}%`} />
          <SubStat label={t("eac.cpiLabel")} value={data.cpi.toFixed(2)} />
          <SubStat
            label={t("eac.varianceLabel")}
            value={formatRubCompact(Math.abs(data.vac))}
            tone={variancePositive ? "good" : "critical"}
            prefix={variancePositive ? "+" : "−"}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={
        "rounded-md border p-2 " +
        (highlight
          ? "border-primary/30 bg-primary/5"
          : "bg-card")
      }
    >
      <div className="text-[11px] text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div className={"text-lg font-semibold " + (highlight ? "text-primary" : "")}>
        {value}
      </div>
    </div>
  );
}

function SubStat({
  label,
  value,
  tone,
  prefix,
}: {
  label: string;
  value: string;
  tone?: "good" | "critical";
  prefix?: string;
}) {
  const toneClass =
    tone === "critical"
      ? "text-rose-600 dark:text-rose-400"
      : tone === "good"
        ? "text-emerald-600 dark:text-emerald-400"
        : "";
  return (
    <div>
      <span className="text-muted-foreground">{label}: </span>
      <span className={"font-medium " + toneClass}>
        {prefix ? prefix : ""}
        {value}
      </span>
    </div>
  );
}
iv>
      <span className="text-muted-foreground">{label}: </span>
      <span className={"font-medium " + toneClass}>
        {prefix ? prefix : ""}
        {value}
      </span>
    </div>
  );
}
