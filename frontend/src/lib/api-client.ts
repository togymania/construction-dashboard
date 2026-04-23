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

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
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
      // Response not JSON, keep statusText
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

import type { Project } from "@/types/project";
import type { DashboardStats } from "@/types/dashboard";
import type { User, TokenResponse } from "@/lib/auth";

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
  },
  dashboard: {
    stats: () => request<DashboardStats>("/dashboard/stats"),
  },
};
