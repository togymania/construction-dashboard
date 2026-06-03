export type SuggestionField = "budget_code" | "subcontractor_id";
export type SuggestionStatus = "pending" | "approved" | "rejected";

export interface MatchSuggestion {
  id: number;
  ledger_entry_id: number;
  field: SuggestionField;
  proposed_value: string;
  candidate_id: number;
  candidate_label: string | null;
  score: number | string;
  reason: string;
  rationale: string | null;
  status: SuggestionStatus;
  resolved_at: string | null;
  resolved_by: number | null;
  created_at: string;
}
