export type ProjectStatus = "planning" | "active" | "on_hold" | "completed" | "cancelled";
export type ProjectHealth = "on_track" | "at_risk" | "delayed";

export interface Project {
  id: number;
  name: string;
  description: string | null;
  status: ProjectStatus;
  health: ProjectHealth;
  budget_usd: number;
  budget_spent_usd: number;
  start_date: string;
  end_date: string;
  progress_pct: number;
  location: string;
}
