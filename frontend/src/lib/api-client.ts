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

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new ApiError(response.status, text || "API request failed");
  }

  return response.json() as Promise<T>;
}

import type { Project } from "@/types/project";
import type { DashboardStats } from "@/types/dashboard";

export const api = {
  projects: {
    list: () => request<Project[]>("/projects"),
    get: (id: number) => request<Project>("/projects/" + id),
  },
  dashboard: {
    stats: () => request<DashboardStats>("/dashboard/stats"),
  },
};
