// ---------- Enums (string unions matching backend) ----------
export type WorkforceCategory = "direct" | "indirect" | "subcontractor";
export type WorkforceCompanyLabel = "Monotekstroy" | "Monart";

// ---------- Embedded summaries ----------
export interface CreatorSummary {
  id: number;
  email: string;
  full_name: string;
}

export interface PositionSummary {
  id: number;
  category: WorkforceCategory;
  name: string;
  display_order: number;
}

// ---------- WorkforcePosition ----------
export interface WorkforcePosition {
  id: number;
  category: WorkforceCategory;
  name: string;
  name_normalized: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkforcePositionCreatePayload {
  category: WorkforceCategory;
  name: string;
  display_order?: number;
  is_active?: boolean;
}

export interface WorkforcePositionUpdatePayload {
  category?: WorkforceCategory;
  name?: string;
  display_order?: number;
  is_active?: boolean;
}

// ---------- WorkforceCount ----------
export interface WorkforceCountInput {
  /** Existing position id, OR provide position_name + category for auto-create */
  position_id?: number | null;
  position_name?: string | null;
  category?: WorkforceCategory | null;
  general_staff: number;
  absent?: number;
  leave_sick?: number;
  /** If omitted, computed = general - absent - leave */
  present?: number | null;
}

export interface WorkforceCount {
  id: number;
  general_staff: number;
  absent: number;
  leave_sick: number;
  present: number;
  position: PositionSummary;
}

// ---------- WorkforceSnapshot ----------
export interface WorkforceSnapshotListItem {
  id: number;
  project_id: number;
  snapshot_date: string;
  company_label: WorkforceCompanyLabel;
  source: string;
  source_filename: string | null;
  total_general_staff: number;
  total_absent: number;
  total_leave_sick: number;
  total_present: number;
  direct_present: number;
  indirect_present: number;
  subcontractor_present: number;
  uploaded_by_user: CreatorSummary | null;
  created_at: string;
  updated_at: string;
}

export interface WorkforceSnapshot extends WorkforceSnapshotListItem {
  notes: string | null;
  counts: WorkforceCount[];
}

export interface WorkforceSnapshotCreatePayload {
  snapshot_date: string;          // ISO date YYYY-MM-DD
  notes?: string | null;
  counts: WorkforceCountInput[];
  source?: string;
  source_filename?: string | null;
}

// ---------- KPI bundle (dashboard) ----------
export interface WorkforceKPICategoryToday {
  category: WorkforceCategory;
  present_today: number;
  delta_vs_yesterday: number;
  delta_pct: number | null;
  position_count: number;
}

export interface WorkforceKPICompanyToday {
  company_label: WorkforceCompanyLabel;
  snapshot_date: string | null;
  direct_present: number;
  indirect_present: number;
  subcontractor_present: number;
  total_present: number;
}

export interface WorkforceKPIDailyPoint {
  snapshot_date: string;
  direct_present: number;
  indirect_present: number;
  subcontractor_present: number;
  total_present: number;
}

export interface WorkforceKPIWeeklyBucket {
  week_start: string;
  avg_total_present: number;
  avg_direct: number;
  avg_indirect: number;
  avg_subcontractor: number;
  days_recorded: number;
}

export interface WorkforceKPITopPosition {
  position_id: number;
  position_name: string;
  category: WorkforceCategory;
  present: number;
}

// ---------- Discipline breakdown ----------
export interface WorkforceDisciplinePoint {
  snapshot_date: string;
  electrical: number;
  mechanical: number;
  civil: number;
}

export interface WorkforceDisciplineTodaySummary {
  electrical: number;
  mechanical: number;
  civil: number;
  total_direct: number;
}

// ---------- AI Insights ----------
export interface WorkforceInsight {
  icon: string;
  text: string;
  tone: "positive" | "negative" | "neutral" | "warning";
}

export interface WorkforceInsightsBundle {
  daily: WorkforceInsight[];
  weekly: WorkforceInsight[];
  monthly: WorkforceInsight[];
}

export interface WorkforceKPIBundle {
  project_id: number;
  as_of_date: string | null;
  snapshot_count: number;
  by_category_today: WorkforceKPICategoryToday[];
  by_company_today: WorkforceKPICompanyToday[];
  daily_trend: WorkforceKPIDailyPoint[];
  weekly_buckets: WorkforceKPIWeeklyBucket[];
  top_positions: WorkforceKPITopPosition[];
  discipline_today: WorkforceDisciplineTodaySummary | null;
  discipline_trend: WorkforceDisciplinePoint[];
  insights: WorkforceInsightsBundle | null;
}

// ---------- Excel import ----------
export interface WorkforceImportWarning {
  code: string;
  message: string;
  detail?: Record<string, unknown> | null;
}

export interface WorkforceImportResponse {
  project_id: number;
  snapshot_date: string | null;
  company_label: WorkforceCompanyLabel | null;
  source_filename: string | null;
  success: boolean;
  error: string | null;
  rows_imported: number;
  rows_skipped: number;
  positions_created: number;
  warnings: WorkforceImportWarning[];
  snapshot: WorkforceSnapshot | null;
}

export interface WorkforceMultiImportResponse {
  project_id: number;
  files_total: number;
  files_succeeded: number;
  files_failed: number;
  results: WorkforceImportResponse[];
}

// ---------- UI helpers (frontend-only) ----------
export const WORKFORCE_CATEGORY_LABEL: Record<WorkforceCategory, string> = {
  direct: "Direct",
  indirect: "Indirect",
  subcontractor: "Subcontractor",
};

export const WORKFORCE_CATEGORY_DESCRIPTION: Record<WorkforceCategory, string> = {
  direct: "Productive personnel - field workers building on site",
  indirect: "Unproductive personnel - engineers, managers, support staff",
  subcontractor: "Subcontractor productive personnel - third-party crews",
};
