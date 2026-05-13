"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Database, AlertCircle, ArrowRight, CheckCircle2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api-client";

interface DataQualityBundle {
  uncategorized_count: number;
  unassigned_count: number;
  total_entries: number;
  dirty_ratio: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
}

function riskClass(level: DataQualityBundle["risk_level"]): string {
  switch (level) {
    case "HIGH":
      return "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900";
    case "MEDIUM":
      return "border-amber-200 bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900";
    default:
      return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900";
  }
}

/**
 * Dashboard widget summarising "dirty" ledger rows: imports that landed
 * without a budget code or subcontractor link. Deep-links to the
 * Expenses page where the user can bulk-assign in batches.
 */
export function DataQualityCard({
  /** Optional project to link into; when omitted we send the user to
   *  the portfolio-wide expenses view. */
  projectId,
}: {
  projectId?: number;
}) {
  const [data, setData] = useState<DataQualityBundle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api.dashboard
      .dataQuality()
      .then((d) => mounted && setData(d))
      .catch(
        (e) =>
          mounted &&
          setError(e instanceof ApiError ? e.message : "Failed to load data quality")
      );
    return () => {
      mounted = false;
    };
  }, []);

  const dirtyTotal = data ? data.uncategorized_count + data.unassigned_count : 0;
  const isClean = data && dirtyTotal === 0;

  const expensesHref = projectId
    ? `/projects/${projectId}/expenses`
    : "/projects";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Database className="h-4 w-4" />
          Data Quality
        </CardTitle>
        {data ? (
          <Badge variant="outline" className={riskClass(data.risk_level)}>
            {isClean ? "CLEAN" : data.risk_level}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : !data ? (
          <div className="space-y-2">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-4 w-full" />
          </div>
        ) : isClean ? (
          <div className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
            <CheckCircle2 className="h-4 w-4" />
            All ledger rows are categorized and assigned.
          </div>
        ) : (
          <>
            <ul className="space-y-1 text-sm">
              {data.uncategorized_count > 0 ? (
                <li className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-amber-500" />
                  <span className="font-semibold">{data.uncategorized_count}</span>
                  <span className="text-muted-foreground">
                    expense{data.uncategorized_count === 1 ? "" : "s"} without a budget code
                  </span>
                </li>
              ) : null}
              {data.unassigned_count > 0 ? (
                <li className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-amber-500" />
                  <span className="font-semibold">{data.unassigned_count}</span>
                  <span className="text-muted-foreground">
                    payment{data.unassigned_count === 1 ? "" : "s"} unlinked from a subcontractor
                  </span>
                </li>
              ) : null}
            </ul>
            <Link
              href={expensesHref}
              className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              Clean up
              <ArrowRight className="h-3 w-3" />
            </Link>
          </>
        )}
      </CardContent>
    </Card>
  );
}
