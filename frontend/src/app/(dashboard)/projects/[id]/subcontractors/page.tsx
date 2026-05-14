"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  HardHat,
  Plus,
  Search,
  Users,
  FileText,
  Wallet,
  TrendingUp,
  AlertCircle,
  Star,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  StatusBadge,
  SUBCONTRACTOR_STATUS_COLORS,
} from "@/components/ui/status-badge";

import { api } from "@/lib/api-client";
import { formatRubCompact } from "@/lib/formatters";
import { useUser } from "@/components/providers/user-provider";
import { useT } from "@/lib/i18n/provider";
import { SpecializationCombobox } from "@/components/subcontractors/specialization-combobox";
import { SubcontractorFormDialog } from "@/components/subcontractors/subcontractor-form-dialog";
import { KpiCharts } from "@/components/subcontractors/kpi-charts";
import type {
  SubcontractorListItem,
  SubcontractorKPIs,
  SubcontractorStatus,
} from "@/types/subcontractor";
import { useParams } from "next/navigation";

export default function SubcontractorsPage() {
  const { user } = useUser();
  const { t } = useT();
  const params = useParams<{ id: string }>();
  const projectId = parseInt(params.id, 10);
  const canEdit =
    user && (user.role === "admin" || user.role === "project_manager");

  const [items, setItems] = useState<SubcontractorListItem[] | null>(null);
  const [kpis, setKpis] = useState<SubcontractorKPIs | null>(null);
  const [specOptions, setSpecOptions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [specFilter, setSpecFilter] = useState<string | null>(null);

  // Form dialog state
  const [formOpen, setFormOpen] = useState(false);

  // Debounced search
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 250);
    return () => clearTimeout(t);
  }, [search]);

  async function loadAll() {
    setError(null);
    try {
      const params: Record<string, string | undefined> = {};
      const filterParams: {
        status?: SubcontractorStatus;
        specialization?: string;
        search?: string;
      } = {};
      if (statusFilter !== "all") filterParams.status = statusFilter as SubcontractorStatus;
      if (specFilter) filterParams.specialization = specFilter;
      if (debouncedSearch.trim()) filterParams.search = debouncedSearch.trim();

      const [list, kpiData, specs] = await Promise.all([
        api.subcontractors.list(filterParams),
        api.subcontractors.kpis(),
        api.subcontractors.specializations(),
      ]);
      setItems(list);
      setKpis(kpiData);
      setSpecOptions(specs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch, statusFilter, specFilter]);

  const totalShown = items?.length ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <HardHat className="h-6 w-6" />
            {t("pages.subcontractors")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t("pages.subcontractorsSubtitle")}
          </p>
        </div>
        {canEdit && (
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            {t("subs.newSubcontractor")}
          </Button>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KpiCard
          icon={<Users className="h-4 w-4 text-muted-foreground" />}
          label={t("subs.totalSubcontractors")}
          value={kpis ? String(kpis.total_subcontractors) : null}
        />
        <KpiCard
          icon={<FileText className="h-4 w-4 text-muted-foreground" />}
          label={t("subs.activeContracts")}
          value={kpis ? String(kpis.active_contracts) : null}
          subline={
            kpis && kpis.overdue_contracts > 0
              ? `${kpis.overdue_contracts} ${t("subs.overdueLabel")}`
              : undefined
          }
          sublineColor="text-red-600 dark:text-red-400"
        />
        <KpiCard
          icon={<AlertCircle className="h-4 w-4 text-muted-foreground" />}
          label={t("subs.overdueContracts")}
          value={kpis ? String(kpis.overdue_contracts) : null}
          highlight={kpis ? kpis.overdue_contracts > 0 : false}
        />
        <KpiCard
          icon={<Wallet className="h-4 w-4 text-muted-foreground" />}
          label={t("subs.totalContractValue")}
          value={kpis ? formatRubCompact(kpis.total_contract_value) : null}
        />
        <KpiCard
          icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
          label={t("subs.paymentProgress")}
          value={kpis ? kpis.payment_completion_pct.toFixed(1) + "%" : null}
          subline={
            kpis ? `${formatRubCompact(kpis.total_paid)} ${t("subs.paid")}` : undefined
          }
        />
      </div>

      {/* KPI Charts */}
      <KpiCharts kpis={kpis} />

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t("subs.searchPlaceholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder={t("subs.allStatuses")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("subs.allStatuses")}</SelectItem>
                <SelectItem value="active">{t("status.active")}</SelectItem>
                <SelectItem value="suspended">{t("status.suspended")}</SelectItem>
                <SelectItem value="blacklisted">{t("status.blacklisted")}</SelectItem>
              </SelectContent>
            </Select>
            <SpecializationCombobox
              options={specOptions}
              value={specFilter}
              onChange={setSpecFilter}
              placeholder={t("subs.allSpecializations")}
            />
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">
            {items === null ? t("status.loading") : `${totalShown} ${t("subs.totalSubcontractors").toLowerCase()}`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <p className="text-sm text-destructive mb-4">{error}</p>
          )}

          {items === null ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <HardHat className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p>{t("subs.emptyHint")}</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("subs.colName")}</TableHead>
                  <TableHead>{t("subs.colSpecialization")}</TableHead>
                  <TableHead>{t("subs.colStatus")}</TableHead>
                  <TableHead className="text-right">{t("subs.activeContracts")}</TableHead>
                  <TableHead className="text-right">{t("subs.totalContractValue")}</TableHead>
                  <TableHead>{t("subs.colActions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer hover:bg-muted/40"
                  >
                    <TableCell>
                      <Link
                        href={`/projects/${projectId}/subcontractors/${item.id}`}
                        className="font-medium hover:underline"
                      >
                        {item.name}
                      </Link>
                      {item.tax_id && (
                        <div className="text-xs text-muted-foreground">
                          {t("subs.taxId")}: {item.tax_id}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.specialization ?? "-"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        status={item.status}
                        colorMap={SUBCONTRACTOR_STATUS_COLORS}
                        withDot={item.status === "active"}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      {item.active_contract_count}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatRubCompact(item.total_contract_value)}
                    </TableCell>
                    <TableCell>
                      {item.rating ? (
                        <div className="flex items-center gap-1">
                          <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                          <span>{item.rating}</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create / Edit dialog */}
      <SubcontractorFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        subcontractor={null}
        specializations={specOptions}
        onSuccess={loadAll}
      />
    </div>
  );
}

interface KpiCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | null;
  subline?: string;
  sublineColor?: string;
  highlight?: boolean;
}

function KpiCard({ icon, label, value, subline, sublineColor, highlight }: KpiCardProps) {
  return (
    <Card className={highlight ? "border-red-300 dark:border-red-900 overflow-hidden" : "overflow-hidden"}>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2 pt-5 px-5">
        <CardTitle className="text-xs font-medium text-muted-foreground truncate">
          {label}
        </CardTitle>
        <span className="flex-shrink-0">{icon}</span>
      </CardHeader>
      <CardContent className="pt-0 pb-5 px-5">
        {value === null ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <div className="text-2xl font-bold tabular-nums font-heading leading-tight truncate">
            {value}
          </div>
        )}
        {subline && (
          <p className={"text-[11px] mt-1.5 truncate " + (sublineColor ?? "text-muted-foreground")}>
            {subline}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
