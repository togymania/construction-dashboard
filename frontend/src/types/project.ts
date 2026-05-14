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

// ---------- AI Project Analysis (6-section structured) ----------

export type DataQualityRisk = "LOW" | "MEDIUM" | "HIGH";
export type FinancialStatus = "OVER_BUDGET" | "ON_TRACK" | "UNDER_BUDGET" | "UNKNOWN";
export type ProductivityStatus = "GOOD" | "AVERAGE" | "LOW" | "UNKNOWN";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type AIProjectStatus = "GOOD" | "WARNING" | "CRITICAL";

export interface CriticalDelay {
  subcontractor: string;
  contract_id: number | null;
  days: number;
  reason: string;
}

export interface DisciplineDelay {
  discipline: string;
  delayed_count: number;
  delay_days: number;
}

export interface ScheduleSection {
  delayed_contracts: number;
  total_contracts: number;
  critical_delays: CriticalDelay[];
  discipline_delays: DisciplineDelay[];
  total_delay_days: number;
}

export interface SuggestedMatch {
  entry_id: number | null;
  description: string;
  suggested_target: string;
  confidence: number;
}

export interface DataQualitySection {
  uncategorized_count: number;
  unassigned_count: number;
  suggested_matches: SuggestedMatch[];
  risk_level: DataQualityRisk;
}

export interface FinancialSection {
  progress_pct: number;
  budget_used_pct: number;
  bac: string | number;
  ac: string | number;
  eac: string | number;
  variance: string | number;
  status: FinancialStatus;
}

export interface ProductivitySection {
  headcount: number;
  man_hours: number;
  productivity: number | null;
  deviation_pct: number | null;
  status: ProductivityStatus;
}

export interface TopRisk {
  title: string;
  impact: string;
  cause: string;
}

export interface RiskSection {
  overall_risk: RiskLevel;
  predicted_delay_days: number;
  top_risks: TopRisk[];
}

export interface ExecutiveSection {
  project_status: AIProjectStatus;
  biggest_problem: string;
  financial_status: string;
  schedule_status: string;
  urgent_action: string;
  summary: string;
}

export interface ProjectAIAnalysis {
  project_id: number;
  generated_at: string;
  lang: "EN" | "TR";
  source: "llm" | "rule";
  schedule: ScheduleSection;
  data_quality: DataQualitySection;
  financial: FinancialSection;
  productivity: ProductivitySection;
  risk: RiskSection;
  executive: ExecutiveSection;
}
