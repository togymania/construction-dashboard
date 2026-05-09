export interface KPIMetric {
  label: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
}

export interface DashboardStats {
  active_projects: KPIMetric;
  total_budget: KPIMetric;
  on_track: KPIMetric;
  open_risks: KPIMetric;
}

// ---------- Daily AI Briefing (Faz 4) ----------

export interface DailyBriefing {
  generated_at: string;
  headline: string;
  summary: string;
  highlights: string[];
  decisions: string[];
  facts: Record<string, number | string>;
  source: "rule" | "llm";
}
