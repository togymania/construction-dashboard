# Monartstroy PM AI — Teknik Sistem Dokümanı

*İnşaat proje kontrolü, maliyet mühendisliği ve karar destek sistemi.*

---

## 1. Proje Genel Bakış

### 1.1 Sistemin Amacı

Sistem, yapım aşamasındaki büyük ölçekli inşaat projelerinde, sahadan toplanan ham finansal ve operasyonel verilerin (Excel gelir-gider defteri, ÇMI bütçe tablosu, taşeron kontrat metadatası, günlük puantaj, ihale dosyaları) tek bir veri modelinde birleştirilmesini, üzerinde determinist hesapların ve LLM tabanlı yargı katmanının çalıştırılmasını ve sonucun karar verici düzeyinde tek bir yargı (verdict) olarak sunulmasını sağlar.

Tasarım hedefi:

- **Tek doğruluk kaynağı (single source of truth)** kurmak — bir maliyet kaleminin "gerçekleşen" değeri proje çapında tek bir yerden hesaplanır
- **Ham veri ile karar arasındaki mesafenin sıfırlanması** — kullanıcı Excel yüklediği andan itibaren EAC, CPI, cash-flow forecast, AI verdict otomatik güncellenir
- **Geri izlenebilirlik (traceability)** — her aggregate (Toplam Gider, AC, EAC, vs.) en az bir kaynak satıra kadar inilebilecek şekilde tutulur

### 1.2 Hedef Kullanıcı Kitlesi

| Kullanıcı Rolü | Sorumluluk | Sistem Yetkisi |
|---|---|---|
| Proje Direktörü / Yatırımcı | Yargı kararları, kaynak tahsisi | Tam okuma + AI Analysis verdict tüketimi |
| Proje Müdürü (PM) | Bütçe yönetimi, taşeron koordinasyonu | Tüm CRUD + Excel import + ihale onayı |
| Maliyet Mühendisi / Sözleşmeler | Hakediş, sözleşme, ödeme | Bütçe + Taşeron + Harcama CRUD |
| Saha Mühendisi | Puantaj, ilerleme | İşgücü modülü read+upload (workforce_editor) |
| Yatırımcı / Denetçi | Performans izleme | Read-only (VIEWER) |

### 1.3 Temel Değer Önerisi

| Mevcut Pratik | Sistem Cevabı |
|---|---|
| Her departman ayrı Excel tutar, PM verileri elle birleştirir | Tek Excel yüklenir, sistem ilişkilendirir |
| EAC / CPI hesaplanmaz veya ay sonu manuel hesaplanır | Her data değişikliğinde gerçek zamanlı |
| Tender analizi 1-2 günlük inşaat mühendisi işidir | PDF/Excel yüklenir, AI 10 sn'de line item bazında karşılaştırır |
| Yönetici raporları statik PowerPoint'tir | Her run'da yeniden hesaplanan "verdict + 3 action" sayfası |
| Veri güvenilirliği görünmez | Data Reliability Score açıkça raporlanır, eşik altındaysa finansal yorum yapılmaz |

---

## 2. Sistem Mimarisi

### 2.1 Katmanlar

```
┌─────────────────────────────────────────────────────────┐
│  Sunum Katmanı — Next.js 16 / React 19 (SPA, SSR)       │
│  Route'lar: /projects/{id}/{module}                      │
└──────────────────┬──────────────────────────────────────┘
                   │ REST (JSON, JWT auth)
┌──────────────────▼──────────────────────────────────────┐
│  Uygulama Katmanı — FastAPI 0.115                        │
│  • REST endpoints (api/v1/*)                             │
│  • Domain services (project_ai_analysis, cashflow_…)     │
│  • Parsers (ledger_excel, financial_summary, monart_…)   │
│  • AI istemcisi (Anthropic Claude)                       │
│  • Insights cache (15 dk TTL)                            │
└──────────────────┬──────────────────────────────────────┘
                   │ SQLAlchemy 2.0 async + Alembic
┌──────────────────▼──────────────────────────────────────┐
│  Veri Katmanı — PostgreSQL                               │
│  • Operasyonel tablolar: project, budget_item,           │
│    subcontractor_contract, subcontractor_payment,        │
│    ledger_entry, expense, workforce_snapshot,            │
│    tender, tender_line_item, bid, bid_line_item          │
│  • Tek-snapshot aggregate: financial_summary             │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Ana Modüller

| Modül | Domain Sorumluluğu | Birincil Tablo(lar) |
|---|---|---|
| **Project** | Proje master kaydı, ilerleme yüzdesi, sağlık etiketi | `projects` |
| **Subcontractors** | Taşeron firma, kontratlar, ödemeler, risk skoru | `subcontractors`, `subcontractor_contracts`, `subcontractor_payments` |
| **Workforce** | Günlük puantaj, dilim bazlı (direct/indirect/subcont.) | `workforce_positions`, `workforce_snapshots` |
| **Budget** | Bütçe kalemleri, kategori, ÇMI master bütçe importu | `budget_items`, `budget_categories` |
| **Expenses (Ledger)** | Banka extresi tarzı kayıtlar, gelir-gider | `ledger_entries`, `expenses` |
| **Financial Summary (OZET)** | Şirket bazlı dönemsel finansal özet | `financial_summaries` |
| **Tenders** | Teklif karşılaştırma, AI extraction, bid analysis | `tenders`, `tender_line_items`, `bids`, `bid_line_items` |
| **AI Analysis** | Determinist KPI hesabı + LLM yargı katmanı | (in-memory cache + project_ai_analysis service) |
| **EAC Widget** | Earned Value bileşenleri | (computed from BudgetItem + OZET) |

### 2.3 Kullanıcı–Sistem Etkileşimi

İki temel etkileşim kalıbı:

**(A) Excel-driven ingest:**
1. Kullanıcı `Harcama Takip-HIPODROM-Monart.xlsx` veya `...-Monotek.xlsx` yükler
2. Sistem dosyayı stream eder (openpyxl `read_only=True`, 10+ MB dosyalar OOM olmadan)
3. **Gelir-Gider** sayfasındaki her satır `LedgerEntry` olarak parse edilir, deduplicate edilir (dedup_hash), commit edilir
4. **OZET** sayfasındaki kalemler `FinancialSummary` upsert edilir (anahtar: project_id + company_label)
5. Otomatik tetiklenen güncellemeler: top KPI'lar, EAC widget, Budget Total Spent, AI Analysis cache invalidation

**(B) Read-only sorgu:**
- Kullanıcı bir modül sayfasını açar, frontend tüm aggregate'leri tek `GET` ile çeker
- Backend cache'den (insights_cache, 15 dk TTL) veya canlı hesaplamadan döner

### 2.4 Veri Akışı (Input → Process → Output)

```
INPUT                              PROCESS                            OUTPUT
─────────                          ─────────                          ─────────
Excel (Gelir-Gider)    ──┐
Excel (OZET)             ├──► parse → dedupe → upsert ──► aggregate hesap ──► EAC
Manuel kontrat kaydı   ──┘                              ──► CPI, Variance
Günlük puantaj         ─────► workforce_snapshot     ──► Productivity KPI
PDF/Excel tender       ─────► Claude extraction       ──► line items + bids
ÇMI master bütçe       ─────► filtre (sorumlu=Монарт) ──► budget_items
                                                       ──► AI verdict (LLM)
                                                       ──► cash-flow forecast
```

---

## 3. Maliyet ve Finans Yönetimi Mantığı

### 3.1 Maliyet Tahmini (Cost Estimating)

Sistem **bottom-up** estimating mantığını kabul eder:

- **Budget at Completion (BAC)** = `Σ BudgetItem.planned_amount` (proje bazında)
- BAC = 0 ise fallback olarak `project.budget_rub` (top-level ceiling) kullanılır
- Bottom-up kaynak: ÇMI master Excel'inde "Bütçe sorumlusu = Монарт" satırları
- Kategorize etme: 15 üst kategori (Bina, Yollar, Altyapı, Haberleşme, Isıtma, Elektrik, Peyzaj, Aydınlatma, Diğer İnşaat) ve 6 default (Labor, Materials, Equipment, Subcontractor, Permits, Other) — cost code prefix'ine göre

**Eksik:** Parametrik tahmin (cost-per-unit, m²/m³ bazlı), analog estimating veya tarihsel veri tabanı yok. WBS hiyerarşisi sadece tek seviye (kategori → kalem).

### 3.2 Bütçe Planlama Mantığı

- **Granülerlik:** Her `BudgetItem` için `planned_amount`, `committed_amount`, `cost_code` (cmi kodu), `category_id`, `notes` (alt detay)
- **Kontrol seviyesi:** Kalem (item) seviyesi. Alt detaylar parent'ın notes alanında bullet olarak tutulur (folded subtotals) — re-baseline veya CMP (Change Management) henüz yok
- **Committed:** Açık alan, sözleşme tutarı için ayrılmış. Kontrat oluşturulduğunda otomatik artırma yok — manuel set ediliyor (eksik)
- **Re-baseline:** Yok. Plan değiştirildiğinde geçmiş plan saklanmıyor

### 3.3 Nakit Akışı Takibi (Cash Flow)

Cash-flow iki perspektiften ölçülür:

**(a) Geçmiş (Actual):**
- `LedgerEntry` (EXPENSE / INCOME) — banka extresinden import
- `SubcontractorPayment` (PAID / APPROVED / PENDING) — formal hakediş
- `FinancialSummary` (OZET) — şirket bazlı dönemsel snapshot

**(b) Gelecek (Forecast) — yalnız taşeron ödemeleri için aktif:**
Per-sub 3 aylık tahmin formülü (`cashflow_forecast.build_forecast`):

```
base_level   = EMA(values[-3:], span=3)               # exp. moving average
trend        = LeastSquaresSlope(values)              # ±25% × base_level ile kapped
season_q     = avg(history_in_Qx) / mean(history)     # [0.5, 1.5] aralığına kapped

likely_i  = max(0, base_level + trend·i) · season_q
worst_i   = max(0, 0.7·base_level + 0.5·trend·i) · min(season_q, 1.0)
best_i    = max(0, 1.2·base_level + 1.3·trend·i) · max(season_q, 1.0)

# Kontrat kapasitesi tavanı (cumulative):
if Σ(likely_1..i) > remaining_capacity:
    scale_down proportionally
```

Where `i ∈ {1, 2, 3}` (gelecek aylar).

Aggregate forecast = `Σ` per-sub forecast'lar; confidence = magnitude-weighted average.

### 3.4 Maliyet Kontrol Mekanizmaları

| Mekanizma | Uygulama |
|---|---|
| **Earned Value Management** | BAC, AC, EV, CPI, EAC, VAC bileşenleri her sayfada otomatik gösterilir |
| **Variance reporting** | Her budget item için planned vs actual, severity bucket (ok/watch/warn/over) |
| **Threshold alarmı** | EAC > 1.05 × BAC → "OVER_BUDGET", EAC < 0.95 × BAC → "UNDER_BUDGET" |
| **Data quality eşiği** | Eksik veri > %40 → AI finansal yorum yapmıyor ("financials cannot be trusted") |
| **Contract overrun** | `total_paid > contract_amount` veya `end_date < today` → kontrat alarmı |
| **Verdict thresholds** | `projected_delay > 14 gün` → AT_RISK, critical path blocked → CRITICAL |

### 3.5 Risk ve Kontenjan (Contingency) Yönetimi

- **Risk skoru — taşeron seviyesinde:** Geçmişin ödeme disiplini, kontrat overrun ratio, end_date proximity'ye göre `RiskScore` üretilir
- **Contractor Risk KPI (proje):** Geç kalmış aktif kontratı olan taşeron sayısı (top 5)
- **Forecast belirsizliği:** 3 senaryo (best / likely / worst) bantı + confidence skoru (0.4-0.8 aralığı)

**Eksikler:**
- **Contingency pool** yok — proje bazında ayrılmış yedek bütçe izlenmiyor
- **Risk register / Monte Carlo** yok
- **Schedule contingency** (kritik yol yedek süresi) modellenmiyor — kritik yol "end_date'e 30 gün kala olan kontrat" heuristic'iyle yaklaşıklanıyor

---

## 4. Kullanılan Analitik Modeller

### 4.1 Earned Value Management Formülleri

```
BAC  = Σ BudgetItem.planned_amount           [if 0 → project.budget_rub]
AC   = Σ FinancialSummary.negative_parent_fields
       (firma_odemeleri + ucret_giderleri + vergi_odemeleri +
        banka_giderleri + diger_gelir_giderler, sign-flipped to positive)
       [fallback: ledger EXPENSE join contract.project_id + Expense.project_id]
EV   = BAC × (progress_pct / 100)
CPI  = EV / AC                                [if AC=0 → 1.0]
EAC  = AC + (BAC - EV) / CPI
VAC  = BAC - EAC

Status:
  OVER_BUDGET    if EAC > 1.05 × BAC
  UNDER_BUDGET   if EAC < 0.95 × BAC
  ON_TRACK       otherwise
  UNKNOWN        if BAC = 0
```

### 4.2 AI Analysis — 8 KPI Determinist Hesabı

| KPI | Formül / Kural |
|---|---|
| `schedule_health` | `delay_days = planned_progress_linear - actual_progress`; bucket ok/watch/critical |
| `projected_delay` | `(remaining_work / current_velocity)` günlere extrapolate |
| `critical_path` | Aktif kontratlar arasında `end_date in [project.end_date - 30d, project.end_date]` olan ve gecikmiş varsa BLOCKED |
| `progress` | `project.progress_pct` (saha tarafından girilir, otonom hesaplama yok) |
| `resource_efficiency` | `progress_pct / latest_headcount × 1000` (proxy) |
| `cost_consistency` | `\|ac/bac − progress/100\| > 0.20` → underreported veya overrun_risk |
| `data_reliability` | `(ledger satırları with budget_code AND subcontractor_id) / total ledger satırı × 100` |
| `contractor_risk` | Geç kalmış aktif kontratı olan distinct taşeron sayısı, top 5 |

### 4.3 7 Adımlı Karar Akışı (Decision Flow)

```python
1. data_validation:
     missing_ratio = (uncategorized + unassigned) / total_entries
     confidence = LOW   if missing_ratio > 0.40
                  MEDIUM if 0.20 < missing_ratio ≤ 0.40
                  HIGH   if missing_ratio ≤ 0.20

2. schedule_check:
     planned_progress_today = linear_interp(start, end, today)
     delay = planned - actual

3. critical_path:
     blocked = ANY (contract is_critical_proxy AND overdue)

4. resource_efficiency:
     inefficiency_flag = (efficiency < threshold) AND (headcount rising)

5. cost_logic:
     ratio = AC / BAC
     if ratio < progress_pct/100 - 0.20: underreported
     if ratio > progress_pct/100 + 0.20: overrun_risk

6. momentum:
     trend_last_7d = (snapshot_today - snapshot_7d_ago) / snapshot_7d_ago
     declining if trend < 0

7. final_verdict:
     CRITICAL  if project_blocked
     AT_RISK   elif projected_delay > 14
     ON_TRACK  otherwise
```

### 4.4 LLM Yargı Katmanı (Claude Prompt)

- Model: `claude-sonnet-4-5`, max_tokens 2500
- Sistem rolü: *"Senior construction project director. Make decisions, not descriptions."*
- Determinist KPI hesaplamaları LLM'e girdi (`facts`) olarak verilir
- LLM çıktısı **strict JSON envelope**: `verdict`, `headline`, `key_drivers[≤3]`, `critical_blocker`, `impact_delay_days`, `impact_summary`, `data_confidence`, `data_confidence_note`, `required_actions[≤3]`
- LLM'in numeric output'u **trust edilmez** — `bac/ac/eac/cpi/variance` deterministle override edilir; LLM yalnızca narrative'e ve aksiyona izinli
- Fallback: API key yoksa rule-based engine aynı şemayı doldurur

### 4.5 Cashflow Forecast Engine

- Method: EMA (exponential moving average) + linear trend + quarterly seasonality + best/likely/worst senaryo bandı
- Trend cap: `±25% × base_level`
- Season factor cap: `[0.5, 1.5]`
- Confidence:
  - `months_of_data < 12` (insufficient): 0.40-0.65 aralığı, `0.4 + (n-1) × 0.025`
  - `months_of_data ≥ 18`: 0.80
  - `months_of_data ≥ 12`: 0.70
- Kontrat kapasitesi tavanı: `cumulative_likely > remaining_amount` ise tüm senaryolar oransal düşürülür

### 4.6 Variance Report Logic

- Per-item actual = `Σ Expense.PAID (matched by budget_item_id)` + `Σ LedgerEntry.EXPENSE (matched by budget_code = item.cost_code OR BudgetCategory.slug)`
- OZET-override (üst düzey tutarlılık için):
  - `ozet_total_expense > 0` ise: `total_actual ← ozet_total_expense`
  - Per-item actual'lar `share = planned_amount / total_planned` oranıyla yeniden dağıtılır
- Severity bucket: utilization < 80% ok, 80-95% watch, 95-100% warn, >100% over

### 4.7 Heuristic Yaklaşımlar (Açıkça Belirtilmiş)

| Yer | Heuristic | Bilimsel Temel |
|---|---|---|
| Critical path tespiti | `end_date ∈ [project_end − 30d, project_end]` | Yok — gerçek CPM/PDM hesabı yapılmıyor |
| Resource efficiency | `progress / headcount × 1000` | Productivity sektör başına farklı, varsayım |
| Man-hours | `headcount × 10 saat/gün` | Standart Rusya inşaat shift'i; saha bazında değişebilir |
| OZET redistribution | Planned amount oranlı | Gerçek kategori-bazlı maliyet dağılımını yansıtmaz |
| Cost consistency | ±%20 sapma eşiği | Sektör normu, ampirik kalibrasyon yapılmadı |
| Contractor matching | RapidFuzz partial_ratio ≥ 70 | İsim benzerliği — KEP/Vergi No karşılaştırması değil |

---

## 5. İş Akışı (Workflow) Analizi

### 5.1 Proje Oluşturma

```
1. ADMIN/PM → "Yeni Proje" → form: name, description, location,
   status, health, budget_rub, start_date, end_date, progress_pct
2. POST /api/v1/projects (DBSession commit)
3. Proje listesi cache miss → yeni proje görünür
4. Sonraki adımlar:
   - ÇMI Excel yüklenir → budget_items doldurulur
   - Subcontractor master + contracts manuel oluşturulur
   - Excel Harcama Takip yüklendiğinde ledger + OZET dolar
```

### 5.2 Bütçe Oluşturma

**Manuel modu:**
1. `Budget > Yeni Kalem` → category_id + cost_code + planned_amount + committed_amount
2. POST `/projects/{id}/budget-items`
3. Budget Summary endpoint cache invalide

**Excel import modu (ÇMI Monart):**
1. PM → `Budget > Excel Yükle` → `master_cmi.xlsx`
2. POST `/projects/{id}/budget-items/import-cmi` (multipart)
3. Parser: `monart_budget_parser.parse(bytes, sheet_name="ЦМИ", responsible_filter="Монарт")`
4. Filtre: "Bütçe sorumlusu" sütunu = "Монарт"
5. Cost code prefix → 15 üst kategori auto-mapping (`category_for`)
6. Alt detay satırları (cost_code boş) → parent kalemin `notes` alanına bullet
7. Mode = "replace" ise mevcut budget_items silinir; "append" ise dedupe (lowercased cost_code)
8. Bulk commit; aksi takdirde rollback + error rapor

### 5.3 Takip ve Güncelleme

**Günlük döngü:**

| Saat | Aktör | Aksiyon | Sistem Tepkisi |
|---|---|---|---|
| 09:00 | Muhasebe | Harcama Takip Excel'lerini yükler | `LedgerEntry` + `FinancialSummary` upsert; Toplam Gelir/Gider/Net, EAC, Variance recompute |
| 09:30 | Saha sorumlusu | Günlük puantaj Excel'i yükler | `WorkforceSnapshot` insert; KPI'lar (today total, cumulative man-hours) recompute |
| Gün boyu | Sözleşmeler | Yeni kontrat / hakediş ekler | Per-sub paid total, cashflow forecast invalide |
| Öğleden sonra | İhale müh. | Yeni teklif PDF'i yükler | Claude extraction → bid + bid_line_items insert |
| 17:00 | PM / Direktör | AI Analysis → Refresh | Cache miss → fact collection + Claude call → verdict + 8 KPI |

**Cache stratejisi:**

| Anahtar | TTL | Invalidation |
|---|---|---|
| `dashboard.daily_briefing` | 15 dk | force_refresh query |
| `project.ai_analysis` | 15 dk (per project, per lang) | force_refresh |
| `project.executive_report` | 15 dk | force_refresh |
| `subcontractor.ai_insights` | 15 dk | doc upload, contract update |
| `subcontractor.profile_report` | 60 dk | doc upload, extracted_data PATCH |

### 5.4 Raporlama

| Rapor | Endpoint | İçerik |
|---|---|---|
| Daily Briefing | `GET /dashboard/daily-briefing` | 3 paragraflık AI sabah özeti |
| Project Executive Report | `GET /projects/{id}/executive-report` | Sözleşmeler durumu, finans özeti, takvim sapması |
| AI Project Analysis | `GET /projects/{id}/ai-analysis` | 8 KPI + verdict + 3 action |
| Budget Variance | `GET /projects/{id}/budget/variance` | Per-item planned vs actual, severity |
| Budget Summary | `GET /projects/{id}/budget-summary` | Kategori bazlı planned/spent |
| EAC | `GET /projects/{id}/eac` | BAC/AC/EAC/CPI/Variance/Status |
| Cashflow Forecast (per-sub) | `GET /subcontractors/{id}/cashflow-forecast` | 12 ay history + 3 ay tahmin |
| Cashflow Forecast (aggregate) | `GET /subcontractors/cashflow-forecast/aggregate` | Proje çapında toplam |
| Tender AI Analysis | `GET /tenders/{id}/ai-analysis` | 6 bölümlü Claude raporu |

---

## 6. Veri Yapıları

### 6.1 Temel Domain Modelleri

```
Project {
  id, name, description, location, status [planning|active|on_hold|completed|cancelled],
  health [on_track|at_risk|delayed], budget_rub, start_date, end_date, progress_pct
}

BudgetCategory {
  id, name, slug, display_order, is_active
}

BudgetItem {
  id, project_id, category_id, description, cost_code,
  planned_amount, committed_amount, notes
}

Subcontractor {
  id, name, tax_id, contact_person, phone, email,
  specialization, status, rating, is_active
}

SubcontractorContract {
  id, subcontractor_id, project_id, contract_number,
  description, contract_amount, start_date, end_date,
  status [active|draft|completed|cancelled]
}

SubcontractorPayment {
  id, contract_id, amount, payment_date, due_date,
  status [PENDING|APPROVED|PAID]
}

LedgerEntry {
  id, entry_date, company_name, kod, account, description,
  amount, entry_type [INCOME|EXPENSE], dedup_hash,
  budget_code (FK → BudgetItem.cost_code OR Category.slug),
  subcontractor_id, contract_id, source_filename
}

Expense {
  id, project_id, budget_item_id, vendor, amount,
  expense_date, status [PENDING|APPROVED|PAID]
}

FinancialSummary {  -- OZET snapshot
  id, project_id, company_label [Monotek|Monart], as_of_date,
  isveren_tahsilatlari, firma_odemeleri, ucret_giderleri,
  vergi_odemeleri, gelir_vergisi, kdv, faiz_gelirleri,
  banka_giderleri, diger_gelir_giderler, toplam,
  source_filename, uploaded_by
  UNIQUE (project_id, company_label)
}

WorkforceSnapshot {
  id, project_id, snapshot_date, company_label,
  direct_present, indirect_present, subcontractor_present,
  total_present
}

Tender {
  id, project_id, title, status [draft|open|evaluating|awarded|cancelled],
  currency, vat_inclusive, awarded_bid_id, quote_date
}

TenderLineItem {
  id, tender_id, order_num, description, unit, quantity,
  parent_id (hierarchy), notes
}

Bid {
  id, tender_id, company_name, total_amount, currency,
  quote_date, revision_no, supersedes_id, delivery_days, notes
}

BidLineItem {
  id, bid_id, tender_line_item_id,
  labor_unit_price, material_unit_price, total_unit_price,
  total_amount, is_text_price, variant_label
}
```

### 6.2 Veri Birimleri ve Doğrulama

| Alan tipi | Birim | Kural |
|---|---|---|
| Para tutarları | RUB (₽), `Numeric(20,2)` | Hep RUB; multi-currency yok |
| Yüzde | float, 0-100 | Negatif olabilir (variance) |
| Tarih | ISO date | `dd/mm/yyyy` formatında render (`en-GB`) |
| Headcount | int ≥ 0 | Snapshot bazlı; günlük |
| Man-hours | derived = `headcount × 10` | Sabit shift varsayımı |
| KPI status | enum [ok, watch, critical, unknown] | Determinist eşikler |
| Verdict | enum [ON_TRACK, AT_RISK, CRITICAL, UNKNOWN] | Decision flow output |

---

## 7. Sistemin Güçlü Yönleri

### 7.1 Veri Entegrasyonu

- **Tek doğruluk noktası (single source of truth)** — Toplam Gider, EAC AC, Budget Total Spent ve AI Cost Consistency aynı `FinancialSummary` kaydından türetilir. Eski sistemde 6 farklı Excel'de aynı rakam farklı görünüyordu
- **Otomatik dedupe** — `LedgerEntry.dedup_hash` üzerinden duplicate satırlar atlanır
- **Geri izlenebilirlik** — Her `FinancialSummary` ve `LedgerEntry` `source_filename` taşır

### 7.2 Karar Destek Katmanı

- **Determinist + LLM ayrımı** — Sayısal değerler (BAC/AC/CPI) deterministle hesaplanır, LLM yalnızca narrative üretir; halüsinasyon riski izole edilmiştir
- **Veri güveni-aware reasoning** — Data Reliability LOW ise AI explicit olarak "financials cannot be trusted" der, sahte finansal yorum vermez
- **Aksiyon-zorunlu prompt** — Her run en az 3 somut, ölçülebilir aksiyon üretir; "may, might, possibly" yumuşatma kelimeleri yasak

### 7.3 Earned Value Management

- BAC/AC/EV/CPI/EAC/VAC hesabı her güncel snapshot'ta otomatik recompute
- Status threshold'ları (±5% etrafında) standart EVM literatürüyle uyumlu

### 7.4 Ölçeklenebilirlik

- 10+ MB Excel dosyaları stream parse (`read_only=True`) ile 512 MB memory limit'in altında işlenir
- 9000+ ledger entry'lik tabloda pagination + filter combo (date range, kod, taşeron, bütçe-kodsuz tab) sorunsuz çalışır

---

## 8. Zayıf Yönler / Eksikler

### 8.1 Maliyet Mühendisliği Açısından Eksikler

| Konu | Mevcut Durum | Eksiklik |
|---|---|---|
| **WBS hiyerarşisi** | İki seviye (Category → Item); alt detaylar `notes` text alanında | Çok seviyeli WBS, level 3+ kalemler ayrı row değil |
| **Cost breakdown structure (CBS)** | Yalnız `BudgetItem` + `cost_code` | Resource-loaded CBS yok (labor saati, malzeme miktarı, ekipman) |
| **Estimating method ayrımı** | Tek tek planned_amount girişi | Parametrik, analog, three-point estimating modu yok |
| **Schedule (CPM/PDM)** | Yok; "critical path" proxy = end_date'e 30 gün kala kontrat | Gerçek aktivite ağı, float hesabı, dependencies yok |
| **Resource scheduling** | Headcount snapshot, productivity proxy | Crew composition, equipment utilization yok |
| **Earned Value detail** | Project-level | WBS-level EV (item bazlı %, performans) yok |
| **Forecasting derinliği** | EMA + linear trend + quarterly seasonality | Monte Carlo / probabilistic, S-curve forecast yok |
| **Contingency / Reserve** | Yok | Contingency pool, management reserve ayrı bütçe kalemi olarak izlenmiyor |
| **Change Management** | Yok | Re-baseline, change order workflow, approval trail yok |
| **Risk Register** | Sadece kontrat-bazlı alarm | Project-level qualitative + quantitative risk register yok |
| **Cash flow income side** | OZET'te tahsilat var; alacak yaşlandırması yok | DSO / DPO analizi, milestone-billing tahmini yok |

### 8.2 Bilimsel Temele Dayanmayan Varsayımlar

| Varsayım | Yer | Etki |
|---|---|---|
| `headcount × 10 saat` = man-hours | Workforce KPI | Vardiya yapısı projeye göre değişir; ±20% hata payı |
| Critical path ≈ end_date'e 30 gün kala kontrat | AI Critical Path KPI | Gerçek aktivite bağımlılıkları yok; false positive/negative kaçınılmaz |
| Cost consistency eşiği ±%20 | AI Cost KPI | Sektör normuyla ampirik değil; kalibrasyon gerekli |
| Resource efficiency = progress / headcount | AI Resource KPI | Birim productivity gibi davranıyor ama m²/m³ vermiyor; göreli kıyas için OK, absolute değer yanıltıcı |
| Linear progress interpolation (start → end) | Schedule Health | Gerçek inşaat S-curve'lü; başlangıçta yavaş, ortada hızlı, sonda yavaş |
| OZET total expense redistribution proportional by planned | Variance per-item | Hangi kategorinin gerçekten ne harcadığı budget code eşleşmesi olmadan bilinemez |
| RapidFuzz partial_ratio ≥ 70 | Subcontractor matching | İsim benzerliği — vergi no/KEP gibi unique identifier kullanılmıyor |
| `progress_pct` kullanıcı tarafından girilir | EV hesabı | Kullanıcı subjektif girdiği değer, kanıt yok; objektif quantitative %'ye dayalı değil |

### 8.3 Süreçsel Eksikler

- **Audit trail** — Tüm tablolarda `created_at`/`updated_at` var ama "kim ne değiştirdi" history yok (örn. budget_item revisyonları)
- **Approval workflow** — Hakediş, change order, contract amendment için "submitted → approved → released" akışı yok; tek kullanıcı yeterli
- **Multi-project** — Şu an tek proje (Central Moscow Hippodrome). Cross-project portfolio rolüpu, resource sharing yok
- **Multi-currency** — RUB hardcoded, döviz kuru / EUR-USD-TRY dönüşümü yok
- **Notification** — Threshold breach durumunda push/email yok; kullanıcı sayfayı açmak zorunda

### 8.4 Veri Kalitesi Bağımlılığı

- Sistem **veri kalitesinin yansımasını** raporlar (Data Reliability KPI) ama **veriyi temizlemek için otomatik müdahale etmez**. Örneğin 9000 ledger satırından 9189'u "taşeronsuz" ise sistem "low confidence" der ama matching'i kullanıcının manuel yapmasını bekler.
- Bu, sistemin **descriptive** (durum bildirir) olduğunu, **prescriptive normalization** yapmadığını gösterir.

---

## 9. Sayısal Örnek (Mevcut Sistemin Davranışı)

Anlık snapshot (Central Moscow Hippodrome, 14 May 2026):

| Metrik | Değer | Kaynak |
|---|---|---|
| BAC (Planned) | 11.94 B ₽ | Σ BudgetItem.planned_amount (15 kalem) |
| Project budget ceiling | 16.00 B ₽ | project.budget_rub |
| AC (Spent) | 7.33 B ₽ | OZET Σ negative parent fields (Monotek 5.77 B − − Monart 1.06 B negatives = ~7.33B) |
| Progress | 74% | project.progress_pct (kullanıcı girdisi) |
| EV | 8.84 B ₽ | 11.94 × 0.74 |
| CPI | 1.21 | 8.84 / 7.33 |
| EAC | 9.90 B ₽ | 7.33 + (11.94 − 8.84) / 1.21 |
| VAC | +2.04 B ₽ | 11.94 − 9.90 |
| Status | UNDER_BUDGET | EAC < 0.95 × BAC |
| Data Reliability | 0% (LOW) | 70 satır / 8138 ≈ %0.9 bütçe kodu atanmış |
| Verdict (AI) | CRITICAL | Data confidence LOW + 117 gün projected delay |
| Aggregate cashflow (3 ay) | 158.9 M ₽ | Σ per-sub forecasts (yalnız subcontractor-linked) |

Verdict CRITICAL çıkıyor çünkü: AC sistem üzerinden 7.33B görünüyor ama bütçe atamaları sadece %0.9 — data confidence düştüğü için AI cost reporting'e güvenmiyor ve "financials cannot be trusted" çıktısı veriyor.

---

## 10. Mimari Notlar (NotebookLM İçin)

- Sistem **fact-collector + LLM** paterninde çalışır: tüm sayısal değerler determinist `_collect_facts()` ile hesaplanır, LLM yalnızca **narrative + decision** katmanını üretir
- Bu yaklaşım LLM'in halüsinasyon riskini izole eder ama LLM çıktısının kalitesi facts'ın doğruluğuna bağımlıdır
- Veri akışında **commit-write-back** mekanizması yoktur: AI verdict salt-okunur (read-only inference), kullanıcı eylemlerine geri yansımaz
- **Snapshot-based** mimari: OZET dönemsel snapshot (one row per project per company), `WorkforceSnapshot` günlük; aralarındaki interpolasyon explicit yapılmaz, kullanıcı en güncel snapshot'a bakar
- Cache: 15 dk TTL — anlık tutarlılık değil, "near-real-time" garantisi vardır

---

*Doküman versiyon: 15 Mayıs 2026*
*Hazırlandığı dosya: `C:\Projects\construction-dashboard\TECHNICAL_DOC.md`*
