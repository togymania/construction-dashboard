"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Gavel, Plus, Trophy, Users, Trash2 } from "lucide-react";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, ApiError } from "@/lib/api-client";
import { useT } from "@/lib/i18n/provider";
import { useUser } from "@/components/providers/user-provider";
import { formatRubCompact } from "@/lib/formatters";
import type { TenderListItem, TenderStatus } from "@/types/tender";

function statusBadgeClass(status: TenderStatus): string {
  switch (status) {
    case "awarded":
      return "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900";
    case "open":
    case "evaluating":
      return "border-blue-300 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900";
    case "cancelled":
      return "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300";
    default:
      return "border-slate-200 bg-slate-50 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300";
  }
}

export default function TendersListPage() {
  const params = useParams<{ id: string }>();
  const projectId = parseInt(params.id, 10);
  const { t } = useT();
  const { user } = useUser();
  const canEdit =
    !!user && (user.role === "admin" || user.role === "project_manager" || user.role === "engineer");

  const [items, setItems] = useState<TenderListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const d = await api.tenders.listByProject(projectId);
      setItems(d);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load tenders");
    }
  }

  useEffect(() => {
    if (projectId > 0) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleDelete(id: number, title: string) {
    if (!confirm(`Delete tender "${title}"?`)) return;
    try {
      await api.tenders.delete(id);
      toast.success("Tender deleted");
      load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 p-2 text-white shadow-sm">
            <Gavel className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {t("tenders.title") || "Tenders"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {t("tenders.subtitle") ||
                "Compare bids for each work package"}
            </p>
          </div>
        </div>
        {canEdit ? (
          <Link href={`/projects/${projectId}/tenders/new`}>
            <Button size="sm">
              <Plus className="mr-1 h-4 w-4" />
              {t("tenders.newTender") || "New Tender"}
            </Button>
          </Link>
        ) : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All tenders</CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : !items ? (
            <div className="space-y-2">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">
              No tenders yet. Click <strong>New Tender</strong> to upload a
              quotation file or create one by hand.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Items</TableHead>
                  <TableHead className="text-right">Bids</TableHead>
                  <TableHead>Lowest</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((t) => (
                  <TableRow
                    key={t.id}
                    className="cursor-pointer hover:bg-muted/40"
                  >
                    <TableCell>
                      <Link
                        href={`/projects/${projectId}/tenders/${t.id}`}
                        className="font-medium hover:underline"
                      >
                        {t.title}
                        {t.awarded_bid_id ? (
                          <Trophy className="ml-2 inline h-3 w-3 text-amber-500" />
                        ) : null}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={statusBadgeClass(t.status)}
                      >
                        {t.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {t.line_item_count}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className="inline-flex items-center gap-1">
                        <Users className="h-3 w-3 text-muted-foreground" />
                        {t.bid_count}
                      </span>
                    </TableCell>
                    <TableCell>
                      {t.lowest_bid_amount ? (
                        <span>
                          <span className="font-medium">
                            {formatRubCompact(t.lowest_bid_amount)}
                          </span>
                          <span className="ml-1 text-xs text-muted-foreground">
                            ({t.lowest_bid_company})
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(t.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      {canEdit ? (
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            handleDelete(t.id, t.title);
                          }}
                          className="text-muted-foreground transition hover:text-rose-500"
                          title="Delete tender"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
