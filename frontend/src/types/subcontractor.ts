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
