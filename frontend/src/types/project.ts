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
  budget_usd: string;
  budget_spent_usd: string;
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
