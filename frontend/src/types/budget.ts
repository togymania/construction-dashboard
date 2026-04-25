// ---------- Budget Category ----------

export interface BudgetCategory {
  id: number;
  name: string;
  slug: string;
  display_order: number;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BudgetCategoryPayload {
  name: string;
  slug: string;
  display_order: number;
  is_active?: boolean;
}

export interface BudgetCategoryUpdatePayload {
  name?: string;
  slug?: string;
  display_order?: number;
  is_active?: boolean;
}

// ---------- Budget Item ----------

export interface CategorySummary {
  id: number;
  name: string;
  slug: string;
}

export interface BudgetItem {
  id: number;
  project_id: number;
  category_id: number;
  category: CategorySummary;
  description: string;
  planned_amount: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface BudgetItemPayload {
  category_id: number;
  description: string;
  planned_amount: number;
  notes?: string | null;
}

export interface BudgetItemUpdatePayload {
  category_id?: number;
  description?: string;
  planned_amount?: number;
  notes?: string | null;
}

// ---------- Budget Summary ----------

export interface BudgetCategoryBreakdown {
  category_id: number;
  category_name: string;
  category_slug: string;
  planned_amount: string;
  spent_amount: string;
  remaining_amount: string;
  utilization_pct: number;
}

export interface BudgetSummary {
  project_id: number;
  project_budget_rub: string;
  total_planned: string;
  total_spent: string;
  total_pending: string;
  remaining: string;
  utilization_pct: number;
  by_category: BudgetCategoryBreakdown[];
}
