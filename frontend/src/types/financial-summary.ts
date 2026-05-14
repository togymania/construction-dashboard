export interface FinancialSummary {
  id: number;
  project_id: number;
  company_label: string; // "Monotek" | "Monart"
  as_of_date: string; // ISO yyyy-mm-dd

  isveren_tahsilatlari: string; // decimals serialized as strings
  firma_odemeleri: string;
  ucret_giderleri: string;
  vergi_odemeleri: string;
  gelir_vergisi: string;
  kdv: string;
  faiz_gelirleri: string;
  banka_giderleri: string;
  diger_gelir_giderler: string;
  toplam: string;

  source_filename: string | null;
  created_at: string;
  updated_at: string;
}
