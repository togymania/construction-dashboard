import { getToken } from "@/lib/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_V1 = API_BASE_URL + "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = path.startsWith("http") ? path : API_V1 + path;
  const token = typeof window !== "undefined" ? getToken() : null;

  const isFormData = options?.body instanceof FormData;

  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
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

import type { Project } from "@/types/project";
import type { DashboardStats } from "@/types/dashboard";
import type { User, TokenResponse } from "@/lib/auth";
import type {
  BudgetCategory,
  BudgetCategoryPayload,
  BudgetCategoryUpdatePayload,
  BudgetItem,
  BudgetItemPayload,
  BudgetItemUpdatePayload,
  BudgetSummary,
  Expense,
  ExpensePayload,
  ExpenseUpdatePayload,
  ExpenseImportResult,
} from "@/types/budget";

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
  },
  dashboard: {
    stats: () => request<DashboardStats>("/dashboard/stats"),
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
    update: (id: number, data: BudgetItemUpdatePayload) =>
      request<BudgetItem>("/budget-items/" + id, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>("/budget-items/" + id, {
        method: "DELETE",
      }),
    summaryForProject: (projectId: number) =>
      request<BudgetSummary>("/projects/" + projectId + "/budget-summary"),
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
};
