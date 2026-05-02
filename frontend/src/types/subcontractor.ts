// ---------- Enums (string unions matching backend) ----------

export type SubcontractorStatus = "active" | "suspended" | "blacklisted";
export type ContractStatus = "draft" | "active" | "completed" | "terminated";
export type PaymentStatus = "pending" | "approved" | "paid" | "rejected";

// ---------- Embedded summary types ----------

export interface CreatorSummary {
  id: number;
  email: string;
  full_name: string;
}

export interface SubcontractorSummary {
  id: number;
  name: string;
  specialization: string | null;
}

export interface ProjectSummary {
  id: number;
  name: string;
}

export interface ContractMiniSummary {
  id: number;
  contract_number: string | null;
  description: string;
  subcontractor_id: number;
}

// ---------- Subcontractor ----------

export interface Subcontractor {
  id: number;
  name: string;
  tax_id: string | null;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  specialization: string | null;
  status: SubcontractorStatus;
  rating: string | null;          // Numeric -> string
  notes: string | null;
  is_active: boolean;
  created_by: number;
  creator: CreatorSummary | null;
  created_at: string;
  updated_at: string;
  active_contract_count: number;
  total_contract_value: string;   // Numeric -> string
}

export interface SubcontractorListItem {
  id: number;
  name: string;
  tax_id: string | null;
  specialization: string | null;
  status: SubcontractorStatus;
  rating: string | null;
  is_active: boolean;
  active_contract_count: number;
  total_contract_value: string;
  created_at: string;
}

export interface SubcontractorPayload {
  name: string;
  tax_id?: string | null;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  specialization?: string | null;
  status?: SubcontractorStatus;
  rating?: number | null;
  notes?: string | null;
}

export interface SubcontractorUpdatePayload {
  name?: string;
  tax_id?: string | null;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  specialization?: string | null;
  status?: SubcontractorStatus;
  rating?: number | null;
  notes?: string | null;
}

// ---------- Contract ----------

export interface SubcontractorContract {
  id: number;
  subcontractor_id: number;
  project_id: number;
  contract_number: string | null;
  description: string;
  contract_amount: string;        // Numeric -> string
  start_date: string;             // ISO date
  end_date: string;               // ISO date
  status: ContractStatus;
  scope_of_work: string | null;
  notes: string | null;
  created_by: number;
  created_at: string;
  updated_at: string;
  subcontractor: SubcontractorSummary | null;
  project: ProjectSummary | null;
  paid_amount: string;
  pending_amount: string;
  payment_count: number;
  is_overdue: boolean;
}

export interface ContractPayload {
  project_id: number;
  contract_number?: string | null;
  description: string;
  contract_amount: number;
  start_date: string;
  end_date: string;
  status?: ContractStatus;
  scope_of_work?: string | null;
  notes?: string | null;
}

export interface ContractUpdatePayload {
  project_id?: number;
  contract_number?: string | null;
  description?: string;
  contract_amount?: number;
  start_date?: string;
  end_date?: string;
  status?: ContractStatus;
  scope_of_work?: string | null;
  notes?: string | null;
}

// ---------- Payment ----------

export interface SubcontractorPayment {
  id: number;
  contract_id: number;
  payment_number: number;
  description: string;
  amount: string;                 // Numeric -> string
  payment_date: string;           // ISO date
  due_date: string | null;
  status: PaymentStatus;
  invoice_number: string | null;
  notes: string | null;
  approved_by: number | null;
  approved_at: string | null;
  created_by: number;
  created_at: string;
  updated_at: string;
  over_payment_warning: string | null;
}

export interface PaymentPayload {
  payment_number?: number | null; // null -> backend auto-assigns
  description: string;
  amount: number;
  payment_date: string;
  due_date?: string | null;
  status?: PaymentStatus;
  invoice_number?: string | null;
  notes?: string | null;
}

export interface PaymentUpdatePayload {
  description?: string;
  amount?: number;
  payment_date?: string;
  due_date?: string | null;
  status?: PaymentStatus;
  invoice_number?: string | null;
  notes?: string | null;
}

// ---------- KPI Dashboard ----------

export interface TopSubcontractor {
  id: number;
  name: string;
  total_value: string;
  contract_count: number;
}

export interface MonthlyPaymentPoint {
  month: string;                  // YYYY-MM
  amount: string;
  count: number;
}

export interface SubcontractorKPIs {
  total_subcontractors: number;
  active_contracts: number;
  overdue_contracts: number;
  total_contract_value: string;
  total_paid: string;
  total_pending: string;
  payment_completion_pct: number;
  top_subcontractors: TopSubcontractor[];
  contracts_by_status: Record<string, number>;
  payments_by_status: Record<string, string>;  // string because backend Decimal
  monthly_payments: MonthlyPaymentPoint[];
}

// ---------- Financial Intelligence (Phase 1) ----------

export interface ContractForecast {
  contract_id: number;
  contract_amount: string;
  total_paid: string;
  remaining_amount: string;
  payment_progress_pct: number;
  burn_rate_per_day: string;
  avg_daily_payment: string;
  estimated_completion_date: string | null;
  next_30_days_projected: string;
  days_elapsed: number;
  days_remaining: number;
}

export interface MonthlyCashFlowPoint {
  month: string;
  paid_amount: string;
  approved_amount: string;
  pending_amount: string;
}

export interface CashFlowForecastPoint {
  month: string;
  best_case: string;
  likely: string;
  worst_case: string;
  seasonality_factor: number;
}

export interface ContractEndPoint {
  contract_id: number;
  contract_label: string;
  end_date: string;
  remaining_amount: string;
}

export interface CashFlowForecast {
  subcontractor_id: number;
  historical: MonthlyCashFlowPoint[];
  forecast: CashFlowForecastPoint[];
  confidence: number;
  insufficient_data: boolean;
  months_of_data: number;
  insights: string[];
  contract_end_dates: ContractEndPoint[];
  method: "ema_seasonal" | "naive_average" | "none";
}

export interface AggregateForecastContributor {
  subcontractor_id: number;
  name: string;
  forecast_total_likely: string;
  active_contract_count: number;
  insufficient_data: boolean;
}

export interface AggregateCashFlowForecast {
  historical: MonthlyCashFlowPoint[];
  forecast: CashFlowForecastPoint[];
  contributors: AggregateForecastContributor[];
  total_subcontractors: number;
  active_subcontractors: number;
  confidence: number;
  insufficient_data_count: number;
  insights: string[];
}

export interface PaymentDiscipline {
  subcontractor_id: number;
  score: number;
  grade: string;
  overdue_payment_pct: number;
  rejected_payment_pct: number;
  avg_approval_days: number;
  total_payments_evaluated: number;
}

// ---------- Risk & Alert (Phase 2) ----------

export interface ContractAlert {
  level: "critical" | "warning" | "info";
  message: string;
  category: "budget" | "timeline" | "payment";
}

export interface RiskScore {
  subcontractor_id: number;
  score: number;
  level: "critical" | "warning" | "healthy";
  alerts: ContractAlert[];
  summary: string;
}

// ---------- Documents (Phase 3) ----------

export type DocumentType = "CONTRACT" | "INVOICE" | "ADDENDUM" | "REPORT";

export interface ContractDocument {
  id: number;
  contract_id: number;
  file_name: string;
  file_size: number;
  mime_type: string;
  file_type: DocumentType;
  version: number;
  extracted_data: Record<string, unknown> | null;
  uploaded_by: number;
  created_at: string;
  updated_at: string;
}

export interface ExtractedContractData {
  contract_amount: string | null;
  start_date: string | null;
  end_date: string | null;
  company_names: string[];
  payment_terms: string[];
  confidence: number;
  // Day 11 — extended fields (all optional for backwards-compat)
  currency?: string | null;
  company_name?: string | null;
  counterparty_name?: string | null;
  payment_terms_summary?: string | null;
  penalty_clauses?: PenaltyClause[];
  key_dates?: KeyDate[];
  risk_flags?: string[];
  summary?: string | null;
  raw_text_sample?: string | null;
  source?: string;
  extracted_at?: string | null;
}

export interface PenaltyClause {
  trigger: string;
  penalty_type: "percentage" | "fixed" | "other";
  amount: string | null;
  percentage: number | null;
  description: string;
}

export interface KeyDate {
  date: string;
  label: string;
  description?: string | null;
}

// ---------- AI Insights (Phase 4) ----------

export interface AIInsight {
  type: "commentary" | "prediction" | "alert";
  severity: "info" | "warning" | "critical";
  message: string;
  metric_value: number | null;
  generated_at: string;
  // Day 11 — optional richer fields
  category?: "financial" | "schedule" | "risk" | "performance" | null;
  title?: string | null;
  body?: string | null;
  action?: string | null;
  source?: "rule" | "llm" | "llm_mock";
}

export interface SubcontractorInsights {
  subcontractor_id: number;
  insights: AIInsight[];
  overall_health: "good" | "at_risk" | "critical";
}
