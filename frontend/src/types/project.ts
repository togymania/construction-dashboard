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
