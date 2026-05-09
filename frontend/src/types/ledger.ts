// LedgerEntry types — mirrors backend/app/schemas/ledger_entry.py

export type LedgerEntryType = "income" | "expense";

export interface LedgerEntry {
  id: number;
  entry_date: string; // ISO date
  description: string | null;
  company_name: string | null;
  kod: string | null;
  account: string | null;
  amount: string; // Decimal as string from JSON
  entry_type: LedgerEntryType;
  budget_code: string | null;
  subcontractor_id: number | null;
  subcontractor_name: string | null;
  contract_id: number | null;
  contract_number: string | null;
  source_filename: string | null;
  source_row: number | null;
  created_at: string;
}

export interface LedgerEntryUpdatePayload {
  budget_code?: string | null;
  contract_id?: number | null;
  subcontractor_id?: number | null;
}

export interface LedgerBulkAssignPayload {
  entry_ids: number[];
  /** When true, apply `budget_code` (null clears it). */
  set_budget_code?: boolean;
  budget_code?: string | null;
  /** When true, apply `subcontractor_id` (null clears it). */
  set_subcontractor_id?: boolean;
  subcontractor_id?: number | null;
}

export interface LedgerBulkAssignResponse {
  updated: number;
  skipped: number;
  not_found: number[];
}

export interface LedgerListResponse {
  items: LedgerEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface LedgerStats {
  total_income: string;
  total_expense: string;
  net: string;
  entry_count: number;
  pending_budget_code_count: number;
  unmatched_subcontractor_count: number;
}

export interface ParseError {
  source_row: number;
  reason: string;
}

export interface CompanyMatchProposal {
  company_name: string;
  occurrences: number;
  candidate_id: number | null;
  candidate_name: string | null;
  score: number;
  high_confidence: boolean;
}

export interface ImportPreview {
  import_token: string;
  filename: string;
  total_rows_parsed: number;
  income_count: number;
  expense_count: number;
  income_total: string;
  expense_total: string;
  duplicates_in_file: number;
  duplicates_in_db: number;
  rows_to_import: number;
  parse_errors: ParseError[];
  match_proposals: CompanyMatchProposal[];
  unmatched_companies_count: number;
}

export interface AcceptedMatch {
  company_name: string;
  subcontractor_id: number | null;
}

export interface ImportCommitRequest {
  import_token: string;
  accepted_matches: AcceptedMatch[];
}

export interface ImportResult {
  created_count: number;
  skipped_duplicate_count: number;
  linked_to_subcontractor_count: number;
  error_count: number;
  errors: ParseError[];
}

export interface SubcontractorPaymentEntry {
  id: number;
  entry_date: string;
  description: string | null;
  amount: string;
  entry_type: LedgerEntryType;
  kod: string | null;
  contract_id: number | null;
  contract_number: string | null;
  source_row: number | null;
}

export interface LedgerListFilters {
  date_from?: string;
  date_to?: string;
  entry_type?: LedgerEntryType;
  kod?: string;
  has_budget_code?: boolean;
  has_subcontractor?: boolean;
  subcontractor_id?: number;
  search?: string;
  limit?: number;
  offset?: number;
}
