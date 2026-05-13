"use client";

const TOKEN_KEY = "construction_dashboard_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  document.cookie = "auth_token=" + token + "; path=/; max-age=86400; SameSite=Lax";
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  document.cookie = "auth_token=; path=/; max-age=0";
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role:
    | "admin"
    | "project_manager"
    | "engineer"
    | "viewer"
    | "workforce_editor";
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
