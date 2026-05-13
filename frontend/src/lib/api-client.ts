import { getToken } from "@/lib/auth";
import type {
  WorkforceCategory,
  WorkforceImportResponse,
  WorkforceMultiImportResponse,
  WorkforceKPIBundle,
  WorkforcePosition,
  WorkforcePositionCreatePayload,
  WorkforcePositionUpdatePayload,
  WorkforceSnapshot,
  WorkforceSnapshotCreatePayload,
  WorkforceSnapshotListItem,
} from "@/types/workforce";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_V1 = API_BASE_URL + "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Read the user's UI language preference from localStorage. Stays in sync
 * with the LanguageProvider (which uses the same key). Default "EN" so the
 * backend never receives an empty Accept-Language and falls back to its
 * own auto-detect heuristic.
 */
function readUiLang(): string {
  if (typeof window === "undefined") return "EN";
  try {
    return localStorage.getItem("ui-lang-preference") || "EN";
  } catch {
    return "EN";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = path.startsWith("http") ? path : API_V1 + path;
  const token = typeof window !== "undefined" ? getToken() : null;

  const isFormData = options?.body instanceof FormData;

  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    // Tell the backend which language Claude should reply in for any
    // AI-generated text (briefings, insights, executive reports).
    "X-User-Lang": readUiLang(),
    ...(options?.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = "Bearer " + token;
  }

  const response = await fetch(url, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // not JSON
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

import type { Project, ProjectExecutiveReport } from "@/types/project";
import type { DailyBriefing, DashboardStats } from "@/types/dashboard";
import type { User, TokenResponse } from "@/lib/auth";
import type {
  BudgetCategory,
  BudgetCategoryPayload,
  BudgetCategoryUpdatePayload,
  BudgetItem,
  BudgetItemPayload,
  BudgetItemUpdatePayload,
  BudgetSummary,
  BudgetVarianceReport,
  Expense,
  ExpensePayload,
  ExpenseUpdatePayload,
  ExpenseImportResult,
  BudgetImportResult,
  BudgetImportMode,
} from "@/types/budget";
import type {
  AggregateCashFlowForecast,
  CashFlowForecast,
  ContractAlert,
  ContractDocument,
  ContractForecast,
  ContractPayload,
  ContractUpdatePayload,
  MonthlyCashFlowPoint,
  PaymentDiscipline,
  PaymentPayload,
  PaymentUpdatePayload,
  RiskScore,
  Subcontractor,
  SubcontractorContract,
  SubcontractorInsights,
  SubcontractorKPIs,
  SubcontractorListItem,
  SubcontractorPayload,
  SubcontractorPayment,
  SubcontractorProfileReport,
  SubcontractorStatus,
  SubcontractorUpdatePayload,
  ContractStatus,
} from "@/types/subcontractor";
import type {
  ImportCommitRequest,
  ImportPreview,
  ImportResult,
  LedgerBulkAssignPayload,
  LedgerBulkAssignResponse,
  LedgerEntry,
  LedgerEntryUpdatePayload,
  LedgerListFilters,
  LedgerListResponse,
  LedgerStats,
  SubcontractorPaymentEntry,
} from "@/types/ledger";

interface ProjectPayload {
  name: string;
  description?: string | null;
  status: string;
  health: string;
  budget_rub: number;
  start_date: string;
  end_date: string;
  progress_pct: number;
  location: string;
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    register: (data: { email: string; password: string; full_name: string }) =>
      request<TokenResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    me: () => request<User>("/auth/me"),
  },
  projects: {
    list: () => request<Project[]>("/projects"),
    get: (id: number) => request<Project>("/projects/" + id),
    create: (data: ProjectPayload) =>
      request<Project>("/projects", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<ProjectPayload>) =>
      request<Project>("/projects/" + id, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>("/projects/" + id, {
        method: "DELETE",
      }),
    executiveReport: (id: number, forceRefresh = false) =>
      request<ProjectExecutiveReport>(
        "/projects/" + id + "/executive-report" + (forceRefresh ? "?force_refresh=true" : "")
      ),
  },
  dashboard: {
    stats: () => request<DashboardStats>("/dashboard/stats"),
    dailyBriefing: (forceRefresh = false) =>
      request<DailyBriefing>(
        "/dashboard/daily-briefing" + (forceRefresh ? "?force_refresh=true" : "")
      ),
  },
  budgetCategories: {
    list: (includeInactive = false) =>
      request<BudgetCategory[]>(
        "/budget-categories" + (includeInactive ? "?include_inactive=true" : "")
      ),
    create: (data: BudgetCategoryPayload) =>
      request<BudgetCategory>("/budget-categories", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: BudgetCategoryUpdatePayload) =>
      request<BudgetCategory>("/budget-categories/" + id, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>("/budget-categories/" + id, {
        method: "DELETE",
      }),
    reorder: (order: number[]) =>
      request<BudgetCategory[]>("/budget-categories/reorder", {
        method: "PATCH",
        body: JSON.stringify({ order }),
      }),
  },
  budgetItems: {
    listForProject: (projectId: number) =>
      request<BudgetItem[]>("/projects/" + projectId + "/budget-items"),
    createForProject: (projectId: number, data: BudgetItemPayload) =>
      request<BudgetItem>("/projects/" + projectId + "/budget-items", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (projectId: number, id: number, data: BudgetItemUpdatePayload) =>
      request<BudgetItem>("/projects/" + projectId + "/budget-items/" + id, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (projectId: number, id: number) =>
      request<void>("/projects/" + projectId + "/budget-items/" + id, {
        method: "DELETE",
      }),
    summaryForProject: (projectId: number) =>
      request<BudgetSummary>("/projects/" + projectId + "/budget-summary"),
    varianceForProject: (projectId: number) =>
      request<BudgetVarianceReport>("/projects/" + projectId + "/budget/variance"),
    importExcel: (
      projectId: number,
      file: File,
      overwriteMode: BudgetImportMode = "append",
    ) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("overwrite_mode", overwriteMode);
      return request<BudgetImportResult>(
        "/projects/" + projectId + "/budget-items/import",
        { method: "POST", body: fd },
      );
    },

    /**
     * Import the master ÇMI workbook and pull in only the rows whose
     * "Bütçe sorumlusu" column matches the responsible filter (default
     * "Монарт"). Hierarchical detail rows are folded into each parent's
     * notes field — never imported as separate items.
     */
    importCmiMonart: (
      projectId: number,
      file: File,
      opts: {
        sheetName?: string;
        responsibleFilter?: string;
        overwriteMode?: BudgetImportMode;
      } = {},
    ) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("sheet_name", opts.sheetName ?? "ЦМИ");
      fd.append("responsible_filter", opts.responsibleFilter ?? "Монарт");
      fd.append("overwrite_mode", opts.overwriteMode ?? "append");
      return request<BudgetImportResult>(
        "/projects/" + projectId + "/budget-items/import-cmi",
        { method: "POST", body: fd },
      );
    },
  },
  expenses: {
    listForProject: (
      projectId: number,
      params?: {
        category_id?: number;
        date_from?: string;
        date_to?: string;
        search?: string;
      }
    ) => {
      const qs = new URLSearchParams();
      if (params?.category_id) qs.set("category_id", String(params.category_id));
      if (params?.date_from) qs.set("date_from", params.date_from);
      if (params?.date_to) qs.set("date_to", params.date_to);
      if (params?.search) qs.set("search", params.search);
      const query = qs.toString();
      return request<Expense[]>(
        "/projects/" + projectId + "/expenses" + (query ? "?" + query : "")
      );
    },
    createForProject: (projectId: number, data: ExpensePayload) =>
      request<Expense>("/projects/" + projectId + "/expenses", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    importExcel: (
      projectId: number,
      file: File,
      defaultCategoryId: number
    ) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("default_category_id", String(defaultCategoryId));
      return request<ExpenseImportResult>(
        "/projects/" + projectId + "/expenses/import",
        { method: "POST", body: fd }
      );
    },
    update: (projectId: number, id: number, data: ExpenseUpdatePayload) =>
      request<Expense>("/projects/" + projectId + "/expenses/" + id, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (projectId: number, id: number) =>
      request<void>("/projects/" + projectId + "/expenses/" + id, {
        method: "DELETE",
      }),
  },
  subcontractors: {
    list: (params?: {
      status?: SubcontractorStatus;
      specialization?: string;
      search?: string;
      include_inactive?: boolean;
    }) => {
      const qs = new URLSearchParams();
      if (params?.status) qs.set("status", params.status);
      if (params?.specialization) qs.set("specialization", params.specialization);
      if (params?.search) qs.set("search", params.search);
      if (params?.include_inactive) qs.set("include_inactive", "true");
      const query = qs.toString();
      return request<SubcontractorListItem[]>(
        "/subcontractors" + (query ? "?" + query : "")
      );
    },
    get: (id: number) => request<Subcontractor>("/subcontractors/" + id),
    create: (data: SubcontractorPayload) =>
      request<Subcontractor>("/subcontractors", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: SubcontractorUpdatePayload) =>
      request<Subcontractor>("/subcontractors/" + id, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>("/subcontractors/" + id, {
        method: "DELETE",
      }),
    specializations: () =>
      request<string[]>("/subcontractors/specializations"),
    kpis: () =>
      request<SubcontractorKPIs>("/subcontractors/stats/kpis"),

    contracts: {
      list: (subId: number, statusFilter?: ContractStatus) => {
        const qs = new URLSearchParams();
        if (statusFilter) qs.set("status", statusFilter);
        const query = qs.toString();
        return request<SubcontractorContract[]>(
          "/subcontractors/" + subId + "/contracts" + (query ? "?" + query : "")
        );
      },
      listForProject: (projectId: number, statusFilter?: ContractStatus) => {
        const qs = new URLSearchParams();
        if (statusFilter) qs.set("status", statusFilter);
        const query = qs.toString();
        return request<SubcontractorContract[]>(
          "/projects/" + projectId + "/subcontractor-contracts" + (query ? "?" + query : "")
        );
      },
      get: (subId: number, contractId: number) =>
        request<SubcontractorContract>(
          "/subcontractors/" + subId + "/contracts/" + contractId
        ),
      create: (subId: number, data: ContractPayload) =>
        request<SubcontractorContract>("/subcontractors/" + subId + "/contracts", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (subId: number, contractId: number, data: ContractUpdatePayload) =>
        request<SubcontractorContract>(
          "/subcontractors/" + subId + "/contracts/" + contractId,
          {
            method: "PATCH",
            body: JSON.stringify(data),
          }
        ),
      delete: (subId: number, contractId: number) =>
        request<void>(
          "/subcontractors/" + subId + "/contracts/" + contractId,
          {
            method: "DELETE",
          }
        ),
    },
    payments: {
      list: (subId: number, contractId: number) =>
        request<SubcontractorPayment[]>(
          "/subcontractors/" + subId + "/contracts/" + contractId + "/payments"
        ),
      create: (subId: number, contractId: number, data: PaymentPayload) =>
        request<SubcontractorPayment>(
          "/subcontractors/" + subId + "/contracts/" + contractId + "/payments",
          {
            method: "POST",
            body: JSON.stringify(data),
          }
        ),
      update: (
        subId: number,
        contractId: number,
        paymentId: number,
        data: PaymentUpdatePayload
      ) =>
        request<SubcontractorPayment>(
          "/subcontractors/" + subId + "/contracts/" + contractId + "/payments/" + paymentId,
          {
            method: "PATCH",
            body: JSON.stringify(data),
          }
        ),
      delete: (subId: number, contractId: number, paymentId: number) =>
        request<void>(
          "/subcontractors/" + subId + "/contracts/" + contractId + "/payments/" + paymentId,
          {
            method: "DELETE",
          }
        ),
    },
    // ===== Financial Intelligence (Phase 1) =====
    forecast: (subId: number, contractId: number) =>
      request<ContractForecast>(
        "/subcontractors/" + subId + "/contracts/" + contractId + "/forecast"
      ),
    paymentDiscipline: (subId: number) =>
      request<PaymentDiscipline>("/subcontractors/" + subId + "/payment-discipline"),
    cashflow: (subId: number) =>
      request<MonthlyCashFlowPoint[]>("/subcontractors/" + subId + "/cashflow"),
    cashflowForecast: (subId: number) =>
      request<CashFlowForecast>("/subcontractors/" + subId + "/cashflow-forecast"),
    aggregateForecast: () =>
      request<AggregateCashFlowForecast>("/subcontractors/cashflow-forecast/aggregate"),
    // ===== Risk & Alerts (Phase 2) =====
    contractAlerts: (subId: number, contractId: number) =>
      request<ContractAlert[]>(
        "/subcontractors/" + subId + "/contracts/" + contractId + "/alerts"
      ),
    riskScore: (subId: number) =>
      request<RiskScore>("/subcontractors/" + subId + "/risk-score"),
    // ===== Documents (Phase 3) =====
    documents: {
      list: (subId: number, contractId: number) =>
        request<ContractDocument[]>(
          "/subcontractors/" + subId + "/contracts/" + contractId + "/documents"
        ),
      upload: (subId: number, contractId: number, file: File, fileType: string = "CONTRACT") => {
        const fd = new FormData();
        fd.append("file", file);
        return request<ContractDocument>(
          "/subcontractors/" + subId + "/contracts/" + contractId + "/documents?file_type=" + fileType,
          { method: "POST", body: fd }
        );
      },
      download: (docId: number) =>
        API_V1 + "/documents/" + docId + "/download",
      delete: (docId: number) =>
        request<void>("/documents/" + docId, { method: "DELETE" }),
      reExtract: (docId: number) =>
        request<ContractDocument>("/documents/" + docId + "/re-extract", {
          method: "POST",
        }),
      updateExtracted: (docId: number, data: Record<string, unknown>) =>
        request<ContractDocument>("/documents/" + docId + "/extracted-data", {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
    },
    // ===== AI Insights (Phase 4) =====
    aiInsights: (subId: number, forceRefresh: boolean = false) =>
      request<SubcontractorInsights>(
        "/subcontractors/" + subId + "/ai-insights" + (forceRefresh ? "?force_refresh=true" : "")
      ),

    // ===== Profile Report — "Firma Kartviziti" =====
    profileReport: (subId: number, forceRefresh: boolean = false) =>
      request<SubcontractorProfileReport>(
        "/subcontractors/" + subId + "/profile-report" + (forceRefresh ? "?force_refresh=true" : "")
      ),
  },
  workforce: {
    // ===== Positions =====
    listPositions: (params?: { category?: WorkforceCategory; is_active?: boolean }) => {
      const qs = new URLSearchParams();
      if (params?.category) qs.set("category", params.category);
      if (params?.is_active !== undefined) qs.set("is_active", String(params.is_active));
      const tail = qs.toString() ? "?" + qs.toString() : "";
      return request<WorkforcePosition[]>("/workforce/positions" + tail);
    },

    createPosition: (data: WorkforcePositionCreatePayload) =>
      request<WorkforcePosition>("/workforce/positions", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    updatePosition: (positionId: number, data: WorkforcePositionUpdatePayload) =>
      request<WorkforcePosition>("/workforce/positions/" + positionId, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),

    deletePosition: (positionId: number) =>
      request<void>("/workforce/positions/" + positionId, {
        method: "DELETE",
      }),

    // ===== Project-scoped snapshots =====
    listSnapshots: (
      projectId: number,
      params?: { limit?: number; offset?: number }
    ) => {
      const qs = new URLSearchParams();
      if (params?.limit !== undefined) qs.set("limit", String(params.limit));
      if (params?.offset !== undefined) qs.set("offset", String(params.offset));
      const tail = qs.toString() ? "?" + qs.toString() : "";
      return request<WorkforceSnapshotListItem[]>(
        "/projects/" + projectId + "/workforce" + tail
      );
    },

    getSnapshot: (projectId: number, snapshotDate: string) =>
      request<WorkforceSnapshot>(
        "/projects/" + projectId + "/workforce/" + snapshotDate
      ),

    upsertSnapshot: (
      projectId: number,
      data: WorkforceSnapshotCreatePayload
    ) =>
      request<WorkforceSnapshot>("/projects/" + projectId + "/workforce", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    deleteSnapshot: (projectId: number, snapshotDate: string) =>
      request<void>(
        "/projects/" + projectId + "/workforce/" + snapshotDate,
        { method: "DELETE" }
      ),

    // ===== Dashboard KPIs =====
    kpis: (projectId: number) =>
      request<WorkforceKPIBundle>(
        "/projects/" + projectId + "/workforce/kpis"
      ),

    // ===== Excel import =====
    importExcel: (projectId: number, files: File[]) => {
      const fd = new FormData();
      for (const f of files) {
        fd.append("files", f);
      }
      return request<WorkforceMultiImportResponse>(
        "/projects/" + projectId + "/workforce/import",
        {
          method: "POST",
          body: fd,
        }
      );
    },
  },

  // ============================================================
  // Ledger (HIPODROM Excel-imported income/expense)
  // ============================================================
  ledger: {
    list: (filters?: LedgerListFilters) => {
      const qs = new URLSearchParams();
      if (filters) {
        for (const [k, v] of Object.entries(filters)) {
          if (v === undefined || v === null || v === "") continue;
          qs.set(k, String(v));
        }
      }
      const tail = qs.toString() ? "?" + qs.toString() : "";
      return request<LedgerListResponse>("/ledger" + tail);
    },

    stats: (filters?: { date_from?: string; date_to?: string }) => {
      const qs = new URLSearchParams();
      if (filters?.date_from) qs.set("date_from", filters.date_from);
      if (filters?.date_to) qs.set("date_to", filters.date_to);
      const tail = qs.toString() ? "?" + qs.toString() : "";
      return request<LedgerStats>("/ledger/stats" + tail);
    },

    update: (entryId: number, data: LedgerEntryUpdatePayload) =>
      request<LedgerEntry>("/ledger/" + entryId, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),

    bulkAssign: (data: LedgerBulkAssignPayload) =>
      request<LedgerBulkAssignResponse>("/ledger/bulk-assign", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    importPreview: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return request<ImportPreview>("/ledger/import/preview", {
        method: "POST",
        body: fd,
      });
    },

    importCommit: (data: ImportCommitRequest) =>
      request<ImportResult>("/ledger/import/commit", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    bySubcontractor: (subcontractorId: number) =>
      request<SubcontractorPaymentEntry[]>(
        "/ledger/by-subcontractor/" + subcontractorId
      ),
  },
};
