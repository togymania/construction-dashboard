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
