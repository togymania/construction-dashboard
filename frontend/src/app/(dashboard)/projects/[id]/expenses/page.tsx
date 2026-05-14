"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Receipt,
  Upload,
  TrendingUp,
  TrendingDown,
  ArrowDownUp,
  ArrowUp,
  ArrowDown,
  Tag,
  HardHat,
  Search,
  ChevronLeft,
  ChevronRight,
  X,
  CheckSquare,
  Square,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { api, ApiError } from "@/lib/api-client";
import { useUser } from "@/components/providers/user-provider";
import { useT } from "@/lib/i18n/provider";
import { useProject } from "@/components/providers/project-provider";
import { formatRub, formatRubCompact } from "@/lib/formatters";
import { LedgerImportWizard } from "@/components/expenses/import-wizard";
import { FinancialSummaryCards } from "@/components/expenses/financial-summary-cards";
import type {
  LedgerEntry,
  LedgerStats,
} from "@/types/ledger";
import type { FinancialSummary } from "@/types/financial-summary";
import type { BudgetCategory } from "@/types/budget";
import type { SubcontractorListItem } from "@/types/subcontractor";

type SortKey = "date" | "amount" | "company" | null;
type SortDir = "asc" | "desc";

type TabKey = "all" | "income" | "expense" | "unassigned" | "unmatched";

const KOD_OPTIONS = [
  "1-HAKEDIS",
  "2-FIRMA",
  "3-UCRET",
  "4-VERGI",
  "6-FAIZ",
  "7-BANKA",
  "8-DIGER",
  "DIGER-HIPODROM",
];

function kodColor(kod: string | null): string {
  if (!kod) return "bg-muted text-muted-foreground";
  if (kod.startsWith("1-")) return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400";
  if (kod.startsWith("2-")) return "bg-blue-500/15 text-blue-700 dark:text-blue-400";
  if (kod.startsWith("3-")) return "bg-purple-500/15 text-purple-700 dark:text-purple-400";
  if (kod.startsWith("4-")) return "bg-amber-500/15 text-amber-700 dark:text-amber-400";
  if (kod.startsWith("6-")) return "bg-rose-500/15 text-rose-700 dark:text-rose-400";
  if (kod.startsWith("7-")) return "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400";
  return "bg-slate-500/15 text-slate-700 dark:text-slate-400";
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function ExpensesPage() {
  const { user } = useUser();
  const { t } = useT();
  const { project } = useProject();
  const projectId = project?.id ?? 0;
  const canImport = user && (user.role === "admin" || user.role === "project_manager");
  const canEdit = user && (user.role === "admin" || user.role === "project_manager");

  const PAGE_SIZE = 100;
  const [stats, setStats] = useState<LedgerStats | null>(null);
  const [entries, setEntries] = useState<LedgerEntry[] | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [error, setError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  // Bump after a successful import to re-fetch the OZET cards (same Excel
  // contains both Gelir-Gider and OZET sheets, so a ledger import may
  // have updated the FinancialSummary row as a side effect).
  const [ozetRefreshKey, setOzetRefreshKey] = useState(0);
  // OZET özet verisi — yukarıdaki Gelir/Gider/Net KPI'ları bu satırlardan
  // hesaplanıyor (positives → gelir, negatives → gider). Fallback: stats.
  const [ozetSummaries, setOzetSummaries] = useState<FinancialSummary[] | null>(
    null,
  );

  const [tab, setTab] = useState<TabKey>("all");
  const [kodFilter, setKodFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  // Sort state — frontend-side sort over the current page.
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Bulk-select state — entries selected for batch assignment.
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Reference data for inline + bulk assign popovers.
  const [budgetCategories, setBudgetCategories] = useState<BudgetCategory[]>([]);
  const [subOptions, setSubOptions] = useState<SubcontractorListItem[]>([]);

  // Track which row is in inline-edit mode (popover open).
  const [editingBudgetFor, setEditingBudgetFor] = useState<number | null>(null);
  const [editingSubFor, setEditingSubFor] = useState<number | null>(null);

  // Bulk popover open state.
  const [bulkBudgetOpen, setBulkBudgetOpen] = useState(false);
  const [bulkSubOpen, setBulkSubOpen] = useState(false);
  const [isApplyingBulk, setIsApplyingBulk] = useState(false);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  async function loadData() {
    setError(null);
    try {
      const filters: Record<string, unknown> = {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      };
      if (tab === "income") filters.entry_type = "income";
      if (tab === "expense") filters.entry_type = "expense";
      if (tab === "unassigned") filters.has_budget_code = false;
      if (tab === "unmatched") filters.has_subcontractor = false;
      if (kodFilter !== "all") filters.kod = kodFilter;
      if (search.trim()) filters.search = search.trim();
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;

      const [statsRes, listRes] = await Promise.all([
        api.ledger.stats({ date_from: dateFrom || undefined, date_to: dateTo || undefined }),
        api.ledger.list(filters),
      ]);
      setStats(statsRes);
      setEntries(listRes.items);
      setTotalCount(listRes.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Veri yüklenirken hata oluştu");
    }
  }

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [tab, kodFilter, dateFrom, dateTo, search]);

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, kodFilter, dateFrom, dateTo, page]);

  // Search debounced apart from filter changes
  useEffect(() => {
    const id = setTimeout(loadData, 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  // OZET summaries — yukarı KPI'lar buradan gelir
  useEffect(() => {
    if (projectId <= 0) return;
    let cancelled = false;
    api.financialSummary
      .list(projectId)
      .then((data) => {
        if (!cancelled) setOzetSummaries(data);
      })
      .catch(() => {
        if (!cancelled) setOzetSummaries([]);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, ozetRefreshKey]);

  function handleImportComplete() {
    setImportOpen(false);
    loadData();
    setOzetRefreshKey((k) => k + 1);
  }

  // ---- Reference data: budget categories + subcontractors (for inline + bulk assign) ----
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cats, subs] = await Promise.all([
          api.budgetCategories.list(),
          api.subcontractors.list(),
        ]);
        if (cancelled) return;
        setBudgetCategories(cats);
        setSubOptions(subs);
      } catch {
        // silently ignore — popovers will show empty state
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ---- Sort handling ----
  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "amount" ? "desc" : "desc");
    }
  }

  const sortedEntries = useMemo(() => {
    if (!entries || sortKey === null) return entries;
    const copy = [...entries];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "date") {
        cmp = a.entry_date.localeCompare(b.entry_date);
      } else if (sortKey === "amount") {
        // Sign-aware: income positive, expense negative
        const av = (a.entry_type === "income" ? 1 : -1) * parseFloat(a.amount);
        const bv = (b.entry_type === "income" ? 1 : -1) * parseFloat(b.amount);
        cmp = av - bv;
      } else if (sortKey === "company") {
        cmp = (a.company_name || "").localeCompare(b.company_name || "");
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [entries, sortKey, sortDir]);

  // ---- Selection ----
  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAllVisible() {
    if (!sortedEntries) return;
    setSelectedIds(new Set(sortedEntries.map((e) => e.id)));
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  function selectByCompany(companyName: string | null) {
    if (!sortedEntries || !companyName) return;
    const ids = sortedEntries
      .filter((e) => (e.company_name || "") === companyName)
      .map((e) => e.id);
    setSelectedIds(new Set(ids));
  }

  function selectByKod(kod: string | null) {
    if (!sortedEntries || !kod) return;
    const ids = sortedEntries.filter((e) => e.kod === kod).map((e) => e.id);
    setSelectedIds(new Set(ids));
  }

  // ---- Single-row inline updates ----
  async function assignBudgetCode(entryId: number, code: string | null) {
    try {
      await api.ledger.update(entryId, { budget_code: code });
      toast.success(code ? `Budget code: ${code}` : "Budget code cleared");
      setEditingBudgetFor(null);
      loadData();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed to update");
    }
  }

  async function assignSubcontractor(entryId: number, subId: number | null) {
    try {
      await api.ledger.update(entryId, { subcontractor_id: subId });
      toast.success(subId ? "Subcontractor assigned" : "Subcontractor cleared");
      setEditingSubFor(null);
      loadData();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed to update");
    }
  }

  // ---- Bulk assignment ----
  async function bulkAssignBudget(code: string | null) {
    if (selectedIds.size === 0) return;
    setIsApplyingBulk(true);
    try {
      const res = await api.ledger.bulkAssign({
        entry_ids: Array.from(selectedIds),
        set_budget_code: true,
        budget_code: code,
      });
      toast.success(`${res.updated} entries updated${res.skipped ? `, ${res.skipped} unchanged` : ""}`);
      setBulkBudgetOpen(false);
      clearSelection();
      loadData();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Bulk update failed");
    } finally {
      setIsApplyingBulk(false);
    }
  }

  async function bulkAssignSub(subId: number | null) {
    if (selectedIds.size === 0) return;
    setIsApplyingBulk(true);
    try {
      const res = await api.ledger.bulkAssign({
        entry_ids: Array.from(selectedIds),
        set_subcontractor_id: true,
        subcontractor_id: subId,
      });
      toast.success(`${res.updated} entries updated${res.skipped ? `, ${res.skipped} unchanged` : ""}`);
      setBulkSubOpen(false);
      clearSelection();
      loadData();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Bulk update failed");
    } finally {
      setIsApplyingBulk(false);
    }
  }

  const allVisibleSelected =
    !!sortedEntries &&
    sortedEntries.length > 0 &&
    sortedEntries.every((e) => selectedIds.has(e.id));

  const kpis = useMemo(() => {
    // Tercih edilen kaynak: OZET satırları (her şirket için Finansal Özet
    // tablosundan). Yeşil rakamlar (pozitif değerler) toplanarak Toplam
    // Gelir, kırmızı rakamlar (negatifler) toplanarak Toplam Gider elde
    // edilir. VERGI ODEMELERI altındaki Gelir Vergisi + KDV sub-item'lar
    // ve TOPLAM sütunu çift saymamak için hariç tutulur.
    if (ozetSummaries && ozetSummaries.length > 0) {
      // Sub-item ve roll-up alanları dışındaki tüm kalemler:
      const PARENT_FIELDS = [
        "isveren_tahsilatlari",
        "firma_odemeleri",
        "ucret_giderleri",
        "vergi_odemeleri",
        "faiz_gelirleri",
        "banka_giderleri",
        "diger_gelir_giderler",
      ] as const;

      let gelir = 0;
      let gider = 0;
      for (const s of ozetSummaries) {
        for (const f of PARENT_FIELDS) {
          const raw = s[f];
          const n = typeof raw === "string" ? parseFloat(raw) : Number(raw);
          if (!isFinite(n) || n === 0) continue;
          if (n > 0) gelir += n;
          else gider += -n; // store as positive
        }
      }
      const net = gelir - gider;

      return [
        {
          label: t("expenses.kpi.totalIncome"),
          value: gelir.toString(),
          icon: TrendingUp,
          accent: "text-emerald-600 dark:text-emerald-400",
        },
        {
          label: t("expenses.kpi.totalExpense"),
          value: gider.toString(),
          icon: TrendingDown,
          accent: "text-rose-600 dark:text-rose-400",
        },
        {
          label: t("expenses.kpi.net"),
          value: net.toString(),
          icon: ArrowDownUp,
          accent:
            net >= 0
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400",
        },
      ];
    }

    // OZET yoksa ledger stats'a düş (geriye dönük uyum)
    if (!stats) return null;
    return [
      {
        label: t("expenses.kpi.totalIncome"),
        value: stats.total_income,
        icon: TrendingUp,
        accent: "text-emerald-600 dark:text-emerald-400",
      },
      {
        label: t("expenses.kpi.totalExpense"),
        value: stats.total_expense,
        icon: TrendingDown,
        accent: "text-rose-600 dark:text-rose-400",
      },
      {
        label: t("expenses.kpi.net"),
        value: stats.net,
        icon: ArrowDownUp,
        accent:
          parseFloat(stats.net) >= 0
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-rose-600 dark:text-rose-400",
      },
    ];
  }, [stats, ozetSummaries, t]);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Receipt className="h-6 w-6 text-primary" />
            {t("expenses.pageTitle")}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("expenses.subtitle")}
          </p>
        </div>
        {canImport && (
          <Button onClick={() => setImportOpen(true)} className="gap-2">
            <Upload className="h-4 w-4" />
            {t("expenses.importButton")}
          </Button>
        )}
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {kpis ? (
          kpis.map((k) => {
            const Icon = k.icon;
            return (
              <Card key={k.label}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {k.label}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <span className={`text-2xl font-semibold ${k.accent}`}>
                      {formatRubCompact(k.value)}
                    </span>
                    <Icon className={`h-5 w-5 ${k.accent}`} />
                  </div>
                </CardContent>
              </Card>
            );
          })
        ) : (
          [0, 1, 2].map((i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Financial Summary (OZET) — Monotek + Monart side-by-side cards */}
      <FinancialSummaryCards projectId={projectId} refreshKey={ozetRefreshKey} />

      {/* Secondary chips */}
      {stats && (
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span className="rounded-md bg-muted px-2.5 py-1.5">
            {stats.entry_count} {t("expenses.kpi.entries")}
          </span>
          <span className="rounded-md bg-amber-500/10 px-2.5 py-1.5 text-amber-700 dark:text-amber-400">
            <Tag className="mr-1 inline h-3 w-3" />
            {stats.pending_budget_code_count} {t("expenses.kpi.noBudget")}
          </span>
          <span className="rounded-md bg-blue-500/10 px-2.5 py-1.5 text-blue-700 dark:text-blue-400">
            <HardHat className="mr-1 inline h-3 w-3" />
            {stats.unmatched_subcontractor_count} {t("expenses.kpi.noSub")}
          </span>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <Tabs value={tab} onValueChange={(v) => setTab(v as TabKey)}>
            <TabsList>
              <TabsTrigger value="all">{t("expenses.tabs.all")}</TabsTrigger>
              <TabsTrigger value="income">{t("expenses.tabs.income")}</TabsTrigger>
              <TabsTrigger value="expense">{t("expenses.tabs.expense")}</TabsTrigger>
              <TabsTrigger value="unassigned">
                {t("expenses.tabs.unassigned")}
              </TabsTrigger>
              <TabsTrigger value="unmatched">
                {t("expenses.tabs.unmatched")}
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="mt-4 flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("expenses.searchPlaceholder")}
                className="pl-9"
              />
            </div>
            <Select value={kodFilter} onValueChange={setKodFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder={t("expenses.kodFilter")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("expenses.kodFilter")}</SelectItem>
                {KOD_OPTIONS.map((k) => (
                  <SelectItem key={k} value={k}>
                    {k}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-[150px]"
            />
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-[150px]"
            />
          </div>
        </CardContent>
      </Card>

      {/* Bulk action bar — sticky at top when rows are selected */}
      {selectedIds.size > 0 && (
        <div className="sticky top-0 z-20 -mx-6 px-6 py-3 bg-primary/95 backdrop-blur-md text-primary-foreground shadow-lg flex items-center gap-3 rounded-md">
          <span className="text-sm font-medium">
            {selectedIds.size} selected
          </span>
          <div className="flex-1" />

          {/* Bulk: assign budget code */}
          <Popover open={bulkBudgetOpen} onOpenChange={setBulkBudgetOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="secondary"
                size="sm"
                className="bg-white/20 hover:bg-white/30 text-primary-foreground border-white/20"
              >
                <Tag className="h-3.5 w-3.5 mr-1.5" />
                Assign budget code
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-64 p-0" align="end">
              <Command>
                <CommandInput placeholder="Search code..." />
                <CommandList>
                  <CommandEmpty>No matches.</CommandEmpty>
                  <CommandGroup>
                    <CommandItem
                      value="__clear__"
                      onSelect={() => bulkAssignBudget(null)}
                    >
                      <X className="h-3.5 w-3.5 mr-2" />
                      Clear budget code
                    </CommandItem>
                    {budgetCategories.map((bc) => (
                      <CommandItem
                        key={bc.id}
                        value={bc.slug}
                        onSelect={() => bulkAssignBudget(bc.slug)}
                        disabled={isApplyingBulk}
                      >
                        <Badge variant="outline" className="mr-2 font-mono text-[10px]">
                          {bc.slug}
                        </Badge>
                        <span className="truncate">{bc.name}</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>

          {/* Bulk: assign subcontractor */}
          <Popover open={bulkSubOpen} onOpenChange={setBulkSubOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="secondary"
                size="sm"
                className="bg-white/20 hover:bg-white/30 text-primary-foreground border-white/20"
              >
                <HardHat className="h-3.5 w-3.5 mr-1.5" />
                Assign subcontractor
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-72 p-0" align="end">
              <Command>
                <CommandInput placeholder="Search subcontractor..." />
                <CommandList>
                  <CommandEmpty>No matches.</CommandEmpty>
                  <CommandGroup>
                    <CommandItem
                      value="__clear__"
                      onSelect={() => bulkAssignSub(null)}
                    >
                      <X className="h-3.5 w-3.5 mr-2" />
                      Clear subcontractor
                    </CommandItem>
                    {subOptions.map((s) => (
                      <CommandItem
                        key={s.id}
                        value={s.name}
                        onSelect={() => bulkAssignSub(s.id)}
                        disabled={isApplyingBulk}
                      >
                        <span className="truncate">{s.name}</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>

          <Button
            variant="ghost"
            size="sm"
            className="text-primary-foreground hover:bg-white/10"
            onClick={clearSelection}
            disabled={isApplyingBulk}
          >
            <X className="h-3.5 w-3.5 mr-1.5" />
            Clear
          </Button>
        </div>
      )}

      {/* Table */}
      <Card>
        <CardContent className="pt-6">
          {error && (
            <div className="rounded-md bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-400">
              {error}
            </div>
          )}

          {entries === null ? (
            <div className="space-y-2">
              {[...Array(8)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <Receipt className="mb-3 h-8 w-8 opacity-40" />
              <p className="text-sm">{t("expenses.empty")}</p>
              <p className="mt-1 text-xs">
                {t("expenses.emptyHint")}
              </p>
            </div>
          ) : (
            <div className="w-full">
              <Table className="w-full table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[44px]">
                      <button
                        type="button"
                        onClick={() => (allVisibleSelected ? clearSelection() : selectAllVisible())}
                        className="inline-flex items-center justify-center text-muted-foreground hover:text-foreground"
                        title={allVisibleSelected ? "Clear selection" : "Select all on this page"}
                      >
                        {allVisibleSelected ? (
                          <CheckSquare className="h-4 w-4 text-primary" />
                        ) : (
                          <Square className="h-4 w-4" />
                        )}
                      </button>
                    </TableHead>
                    <TableHead className="w-[88px]">
                      <SortHeader
                        label={t("expenses.col.date")}
                        active={sortKey === "date"}
                        dir={sortDir}
                        onClick={() => handleSort("date")}
                      />
                    </TableHead>
                    <TableHead className="w-[22%]">
                      <SortHeader
                        label={t("expenses.col.company")}
                        active={sortKey === "company"}
                        dir={sortDir}
                        onClick={() => handleSort("company")}
                      />
                    </TableHead>
                    <TableHead className="w-[90px]">{t("expenses.col.kod")}</TableHead>
                    <TableHead className="w-[90px]">{t("expenses.col.account")}</TableHead>
                    <TableHead>{t("expenses.col.description")}</TableHead>
                    <TableHead className="w-[130px] text-right">
                      <SortHeader
                        label={t("expenses.col.amount")}
                        active={sortKey === "amount"}
                        dir={sortDir}
                        onClick={() => handleSort("amount")}
                        align="right"
                      />
                    </TableHead>
                    <TableHead className="w-[110px]">{t("expenses.col.budget")}</TableHead>
                    <TableHead className="w-[160px]">{t("expenses.col.sub")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(sortedEntries ?? []).map((e) => {
                    const isSelected = selectedIds.has(e.id);
                    return (
                      <TableRow
                        key={e.id}
                        className={isSelected ? "bg-primary/5" : undefined}
                      >
                        <TableCell>
                          <button
                            type="button"
                            onClick={() => toggleSelect(e.id)}
                            className="inline-flex items-center justify-center"
                            aria-label={isSelected ? "Deselect row" : "Select row"}
                          >
                            {isSelected ? (
                              <CheckSquare className="h-4 w-4 text-primary" />
                            ) : (
                              <Square className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                            )}
                          </button>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {formatDate(e.entry_date)}
                        </TableCell>
                        <TableCell className="text-sm font-medium">
                          <button
                            type="button"
                            className="block truncate text-left hover:text-primary transition-colors"
                            title={`Click to select all rows for ${e.company_name || "this company"}`}
                            onClick={() => selectByCompany(e.company_name)}
                          >
                            {e.company_name || "—"}
                          </button>
                        </TableCell>
                        <TableCell>
                          {e.kod ? (
                            <button
                              type="button"
                              onClick={() => selectByKod(e.kod)}
                              title={`Click to select all rows with KOD ${e.kod}`}
                            >
                              <Badge variant="secondary" className={`${kodColor(e.kod)} font-mono text-[10px] whitespace-nowrap cursor-pointer hover:ring-1 hover:ring-primary/40`}>
                                {e.kod}
                              </Badge>
                            </button>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground truncate">
                          {e.account || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          <span className="block truncate" title={e.description || undefined}>
                            {e.description || "—"}
                          </span>
                        </TableCell>
                        <TableCell
                          className={`text-right font-mono text-xs font-medium whitespace-nowrap ${
                            e.entry_type === "income"
                              ? "text-emerald-600 dark:text-emerald-400"
                              : "text-rose-600 dark:text-rose-400"
                          }`}
                        >
                          {e.entry_type === "income" ? "+" : "−"}
                          {formatRub(e.amount).replace(" ₽", "")}
                        </TableCell>
                        {/* Inline budget code edit */}
                        <TableCell>
                          {canEdit ? (
                            <Popover
                              open={editingBudgetFor === e.id}
                              onOpenChange={(open) => setEditingBudgetFor(open ? e.id : null)}
                            >
                              <PopoverTrigger asChild>
                                <button
                                  type="button"
                                  className="inline-flex items-center hover:opacity-80"
                                >
                                  {e.budget_code ? (
                                    <Badge variant="outline" className="text-[10px] cursor-pointer">
                                      {e.budget_code}
                                    </Badge>
                                  ) : (
                                    <span className="text-[10px] text-muted-foreground italic underline-offset-2 hover:underline cursor-pointer">
                                      {t("expenses.col.budgetEmpty")}
                                    </span>
                                  )}
                                </button>
                              </PopoverTrigger>
                              <PopoverContent className="w-64 p-0" align="start">
                                <Command>
                                  <CommandInput placeholder="Search code..." />
                                  <CommandList>
                                    <CommandEmpty>No matches.</CommandEmpty>
                                    <CommandGroup>
                                      <CommandItem
                                        value="__clear__"
                                        onSelect={() => assignBudgetCode(e.id, null)}
                                      >
                                        <X className="h-3.5 w-3.5 mr-2" />
                                        Clear
                                      </CommandItem>
                                      {budgetCategories.map((bc) => (
                                        <CommandItem
                                          key={bc.id}
                                          value={bc.slug}
                                          onSelect={() => assignBudgetCode(e.id, bc.slug)}
                                        >
                                          <Badge variant="outline" className="mr-2 font-mono text-[10px]">
                                            {bc.slug}
                                          </Badge>
                                          <span className="truncate">{bc.name}</span>
                                        </CommandItem>
                                      ))}
                                    </CommandGroup>
                                  </CommandList>
                                </Command>
                              </PopoverContent>
                            </Popover>
                          ) : e.budget_code ? (
                            <Badge variant="outline" className="text-[10px]">{e.budget_code}</Badge>
                          ) : (
                            <span className="text-[10px] text-muted-foreground italic">
                              {t("expenses.col.budgetEmpty")}
                            </span>
                          )}
                        </TableCell>
                        {/* Inline subcontractor edit */}
                        <TableCell>
                          {canEdit ? (
                            <Popover
                              open={editingSubFor === e.id}
                              onOpenChange={(open) => setEditingSubFor(open ? e.id : null)}
                            >
                              <PopoverTrigger asChild>
                                <button
                                  type="button"
                                  className="block w-full text-left hover:opacity-80"
                                  title={e.subcontractor_name || undefined}
                                >
                                  {e.subcontractor_name ? (
                                    <span className="block text-xs text-primary hover:underline truncate cursor-pointer">
                                      {e.subcontractor_name}
                                    </span>
                                  ) : (
                                    <span className="text-xs text-muted-foreground italic underline-offset-2 hover:underline cursor-pointer">
                                      {t("expenses.col.subEmpty") || "Atama yok"}
                                    </span>
                                  )}
                                </button>
                              </PopoverTrigger>
                              <PopoverContent className="w-72 p-0" align="start">
                                <Command>
                                  <CommandInput placeholder="Search subcontractor..." />
                                  <CommandList>
                                    <CommandEmpty>No matches.</CommandEmpty>
                                    <CommandGroup>
                                      <CommandItem
                                        value="__clear__"
                                        onSelect={() => assignSubcontractor(e.id, null)}
                                      >
                                        <X className="h-3.5 w-3.5 mr-2" />
                                        Clear
                                      </CommandItem>
                                      {subOptions.map((s) => (
                                        <CommandItem
                                          key={s.id}
                                          value={s.name}
                                          onSelect={() => assignSubcontractor(e.id, s.id)}
                                        >
                                          <span className="truncate">{s.name}</span>
                                        </CommandItem>
                                      ))}
                                    </CommandGroup>
                                  </CommandList>
                                </Command>
                              </PopoverContent>
                            </Popover>
                          ) : e.subcontractor_name ? (
                            <a
                              href={`/projects/${projectId}/subcontractors/${e.subcontractor_id}`}
                              className="block text-xs text-primary hover:underline truncate"
                              title={e.subcontractor_name}
                            >
                              {e.subcontractor_name}
                            </a>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Pagination */}
          {entries && totalCount > 0 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, totalCount)} / {totalCount}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(1)}
                  disabled={page === 1}
                >
                  «
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="px-2 text-xs tabular-nums">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(totalPages)}
                  disabled={page >= totalPages}
                >
                  »
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {importOpen && (
        <LedgerImportWizard
          projectId={projectId}
          onClose={() => setImportOpen(false)}
          onComplete={handleImportComplete}
        />
      )}
    </div>
  );
}

/**
 * Clickable sort header. Shows an arrow when active.
 */
function SortHeader({
  label,
  active,
  dir,
  onClick,
  align = "left",
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
  align?: "left" | "right";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1 hover:text-foreground transition-colors ${
        align === "right" ? "ml-auto" : ""
      } ${active ? "text-foreground font-medium" : "text-muted-foreground"}`}
    >
      {align === "right" && active ? (
        dir === "asc" ? (
          <ArrowUp className="h-3 w-3" />
        ) : (
          <ArrowDown className="h-3 w-3" />
        )
      ) : null}
      <span>{label}</span>
      {align !== "right" ? (
        active ? (
          dir === "asc" ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )
        ) : (
          <ArrowDownUp className="h-3 w-3 opacity-40" />
        )
      ) : null}
    </button>
  );
}
 