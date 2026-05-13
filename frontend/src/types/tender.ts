// ---------- Tender / Bid module types ----------

export type TenderStatus =
  | "draft"
  | "open"
  | "evaluating"
  | "awarded"
  | "cancelled";

export type BidStatus = "invited" | "received" | "withdrawn" | "selected";

export interface TenderLineItem {
  id: number;
  tender_id: number;
  order_num: number;
  description: string;
  unit: string | null;
  quantity: string; // decimal
  notes: string | null;
}

export interface BidLineItem {
  id: number;
  bid_id: number;
  tender_line_item_id: number;
  unit_price_labor: string | null;
  unit_price_material: string | null;
  unit_price_total: string;
  line_total: string;
  notes: string | null;
}

export interface Bid {
  id: number;
  tender_id: number;
  subcontractor_id: number | null;
  company_name: string;
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  included_in_price: string | null;
  not_included_in_price: string | null;
  payment_terms: string | null;
  delivery_days: number | null;
  notes: string | null;
  status: BidStatus;
  total_labor: string;
  total_material: string;
  total_amount: string;
  received_at: string | null;
  created_at: string;
  updated_at: string;
  line_items: BidLineItem[];
}

export interface Tender {
  id: number;
  project_id: number;
  title: string;
  object_name: string | null;
  description: string | null;
  currency: string;
  payment_terms_expected: string | null;
  delivery_terms_expected: string | null;
  notes: string | null;
  status: TenderStatus;
  awarded_bid_id: number | null;
  source_filename: string | null;
  extracted_by_llm: boolean;
  created_at: string;
  updated_at: string;
  line_items: TenderLineItem[];
  bids: Bid[];
}

export interface TenderListItem {
  id: number;
  project_id: number;
  title: string;
  status: TenderStatus;
  currency: string;
  line_item_count: number;
  bid_count: number;
  lowest_bid_amount: string | null;
  lowest_bid_company: string | null;
  awarded_bid_id: number | null;
  created_at: string;
  updated_at: string;
}

// ---------- AI extraction draft ----------

export interface ExtractedLineItem {
  order_num: number;
  description: string;
  unit: string | null;
  quantity: string;
}

export interface ExtractedBidLine {
  order_num: number;
  unit_price_labor: string | null;
  unit_price_material: string | null;
  unit_price_total: string;
}

export interface ExtractedBid {
  company_name: string;
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  included_in_price: string | null;
  not_included_in_price: string | null;
  payment_terms: string | null;
  delivery_days: number | null;
  notes: string | null;
  lines: ExtractedBidLine[];
}

export interface TenderExtraction {
  title: string;
  object_name: string | null;
  currency: string;
  payment_terms_expected: string | null;
  delivery_terms_expected: string | null;
  notes: string | null;
  line_items: ExtractedLineItem[];
  bids: ExtractedBid[];
  source_filename: string | null;
  source: "llm" | "rule";
  warnings: string[];
}

// ---------- Create / update payloads ----------

export interface TenderLineItemCreate {
  order_num: number;
  description: string;
  unit?: string | null;
  quantity?: string | number;
  notes?: string | null;
}

export interface TenderCreate {
  title: string;
  object_name?: string | null;
  description?: string | null;
  currency?: string;
  payment_terms_expected?: string | null;
  delivery_terms_expected?: string | null;
  notes?: string | null;
  line_items?: TenderLineItemCreate[];
}

export interface BidLineUpsert {
  tender_line_item_id: number;
  unit_price_labor?: string | number | null;
  unit_price_material?: string | number | null;
  unit_price_total?: string | number;
  notes?: string | null;
}

export interface BidCreate {
  company_name: string;
  subcontractor_id?: number | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  included_in_price?: string | null;
  not_included_in_price?: string | null;
  payment_terms?: string | null;
  delivery_days?: number | null;
  notes?: string | null;
  line_items?: BidLineUpsert[];
}

export interface BidUpdate {
  company_name?: string;
  subcontractor_id?: number | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  included_in_price?: string | null;
  not_included_in_price?: string | null;
  payment_terms?: string | null;
  delivery_days?: number | null;
  notes?: string | null;
  status?: BidStatus;
  line_items?: BidLineUpsert[];
}

// ---------- AI Bid Analysis output ----------

export type BidSpreadLevel = "NORMAL" | "WIDE" | "ABNORMAL";

export interface BidSummary {
  company: string;
  total_amount: string;
  delivery_days: number | null;
  is_lowest: boolean;
  is_highest: boolean;
}

export interface TenderOverviewSection {
  title: string;
  bid_count: number;
  average_total: string;
  lowest: BidSummary | null;
  highest: BidSummary | null;
  bid_spread_pct: number;
  bid_spread_level: BidSpreadLevel;
}

export interface ComparisonRow {
  company: string;
  total_amount: string;
  delivery_days: number | null;
  notes: string | null;
}

export interface AnalysisSection {
  best_price_company: string | null;
  fastest_company: string | null;
  most_balanced_company: string | null;
  comments: string | null;
}

export interface RiskItem {
  company: string;
  risk: string;
  cause: string;
}

export interface RecommendationSection {
  chosen_company: string | null;
  reason: string;
  alternative_company: string | null;
  confidence_pct: number;
}

export interface TenderAIAnalysis {
  tender_id: number;
  generated_at: string;
  lang: "EN" | "TR";
  source: "llm" | "rule";
  overview: TenderOverviewSection;
  comparison: ComparisonRow[];
  analysis: AnalysisSection;
  risks: RiskItem[];
  recommendation: RecommendationSection;
  executive_summary: string;
}
