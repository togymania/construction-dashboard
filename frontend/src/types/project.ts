export type ProjectStatus = "planning" | "active" | "on_hold" | "completed" | "cancelled";
export type ProjectHealth = "on_track" | "at_risk" | "delayed";

export interface ProjectOwner {
  id: number;
  email: string;
  full_name: string;
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  status: ProjectStatus;
  health: ProjectHealth;
  budget_rub: string;
  start_date: string;
  end_date: string;
  progress_pct: string;
  location: string;
  owner_id: number;
  owner: ProjectOwner;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ---------- Executive Report (Faz 5) ----------

export interface ExecutiveReportSections {
  executive_summary: string;
  financial_status: string;
  critical_risks: string;
  subcontractor_performance: string;
  workforce_health: string;
  next_30_days: string;
}

export interface ProjectExecutiveReport {
  project_id: number;
  project_name: string;
  generated_at: string;
  headline: string;
  sections: ExecutiveReportSections;
  recommended_actions: string[];
  facts: Record<string, unknown>;
  source: "rule" | "llm";
}

// ---------- AI Project Analysis (v2 -- executive director) ----------
//
// The v2 payload is intentionally small: 8 compact KPIs plus a single
// decisive verdict. The frontend renders the verdict prominently at
// the top and the 8 KPIs as a compact grid below.

export type KPIStatusLevel = "ok" | "watch" | "critical" | "unknown";

export interface KPIStatus {
  /** Stable identifier used by the frontend to bind i18n + icon. */
  key: string;
  /** Display-ready, pre-formatted value (e.g. "+14 d", "78 %"). */
  value: string;
  status: KPIStatusLevel;
  /** English/Turkish fallback label from the backend. */
  label: string;
  /** Short single-sentence explanation. */
  detail: string;
}

export type VerdictLevel = "ON_TRACK" | "AT_RISK" | "CRITICAL" | "UNKNOWN";
export type DataConfidence = "HIGH" | "MEDIUM" | "LOW";

export interface AIVerdict {
  verdict: VerdictLevel;
  headline: string;
  key_drivers: string[];
  critical_blocker: string;
  impact_delay_days: number;
  /** "time" | "cost" | "execution" — risk category. */
  impact_summary: string;
  data_confidence: DataConfidence;
  data_confidence_note: string;
  required_actions: string[];
}

export interface ProjectAIAnalysis {
  project_id: number;
  generated_at: string;
  lang: "EN" | "TR";
  source: "llm" | "rule";
  kpis: KPIStatus[];
  verdict: AIVerdict;
}
