# Day 11 - Subcontractor Intelligence

**Estimated:** ~6 hours of focused work (vs. original 8.5h plan; LLM mock paths
saved ~2.5h that would otherwise be spent on real API integration).
**Goal:** Add three intelligence features for subcontractor management:
PDF contract parsing (mock LLM), seasonal cash flow forecasting, and
contextual rule-based + mock-LLM insights.

## Pre-flight checklist

- Backend on port 8000, frontend on 3000 (start-all.ps1)
- venv activated for any backend python invocation
- Recurring traps to avoid:
  - PowerShell heredoc + multi-line file: prefer python write_bytes helper
  - Indentation match: read the file with view first, never guess
  - Pydantic forward references: define child models before parent models
  - React Fragment: needs `<Fragment key={...}>` not `<>` shorthand for keys
- Sandbox mount truncates files >~12KB when read from bash; use Read tool
  for verification, defer commits to host machine.

## Plan revision (vs. original draft)

Original sequencing M1 (PDF) → M2 (Forecast) → M3 (Insights) revised to
**M2 → M1 → M3** because:
- M2 is the only milestone that fully ships value today (no LLM needed).
- M1 and M3 produce mock LLM output until API key is added — value
  realized when key lands (Day 12).

User decisions made before kickoff:
- **API key:** Not yet obtained; mock everywhere, regex fallback.
- **Seasonality:** Include Q1-Q4 mevsimsellik even on thin data, but
  **must** show "<12 ay veriden uretildi" warning badge.
- **Endpoints:** New endpoints only; old `/cashflow` and `/ai-insights`
  unchanged for backwards-compat.
- **Cache:** In-memory dict, manual "Yenile" button.

## FAZ 2 - Cash Flow Forecast (~2.5 hours)

### 2.1 Backend service (~1 hour)
- New file: `backend/app/services/cashflow_forecast.py`
- Pure function `build_forecast(subcontractor_id, history_rows, contracts)`
  - EMA over last 3 non-zero months (base level)
  - Linear least-squares trend (capped to ±25% of base level)
  - Quarterly seasonality factors (Q1-Q4, capped to [0.5, 1.5])
  - 3 scenarios: best (1.2x base + 1.3x trend) / likely / worst (0.7x base)
  - Cumulative cap by remaining contract capacity (no overshoot)
  - Special case: no active contracts → all-zero forecast, confidence=0.9
- New schemas: `CashFlowForecast`, `CashFlowForecastPoint`, `ContractEndPoint`
- New endpoint: `GET /subcontractors/{id}/cashflow-forecast` →
  CashFlowForecast.

### 2.2 Frontend (~1 hour)
- New types: `CashFlowForecast`, `CashFlowForecastPoint`, `ContractEndPoint`
- `api.subcontractors.cashflowForecast(subId)`
- New component `<CashFlowForecastChart>`:
  - Recharts `ComposedChart` with Bar history + Line × 3 scenarios
    + Area confidence band + ReferenceLine "today" + ReferenceDot
    contract-end markers
  - Confidence badge (color-coded), method label
  - Amber warning when `insufficient_data=true`
  - Insights bullets at bottom
  - Contract-end-dates list
- Integrated above existing detailed monthly bar chart in cash flow tab.

### 2.3 Smoke test (~30 min)
- Unit tests for `build_forecast` with 4 scenarios:
  - 4-month history + active contract
  - 14-month with engineered Q4 dip
  - Empty history
  - 18-month + active contract
- Frontend manual: Atlas Beton (COMPLETED) shows zero, Yılmaz (ACTIVE)
  shows 3-month forecast.

## FAZ 1 - PDF Upload + LLM Extraction (~2 hours, mock LLM)

### 1.1 Backend infrastructure (~45 min)
- `requirements.txt`: add `pdfplumber==0.11.4`, `anthropic==0.39.0`
- `.env`: add `ANTHROPIC_API_KEY=`, `ANTHROPIC_MODEL=claude-sonnet-4-5`,
  `LLM_TIMEOUT_SECONDS=30`, `MAX_PDF_SIZE_MB=20`
- `config.py`: matching Settings fields
- Schema additions to `subcontractor.py`:
  - `PenaltyClause` (trigger, penalty_type, amount?, percentage?, description)
  - `KeyDate` (date, label, description?)
  - `ExtractedContractData` extended with currency, company_name,
    counterparty_name, payment_terms_summary, penalty_clauses, key_dates,
    risk_flags, summary, raw_text_sample, source, extracted_at — all optional
- `contract_parser.py` split:
  - `extract_text_from_pdf(bytes) -> str` (pdfplumber)
  - `parse_contract_with_llm(text, api_key=None) -> dict`
    - When `api_key` empty: synthetic mock blending regex + placeholder
      structured fields; `source=llm_mock`
    - When `api_key` present: real Anthropic call with extraction prompt
    - On any LLM exception: regex-only fallback, low confidence

### 1.2 Endpoints (~30 min)
- Existing `upload_document`: dispatch on PDF content_type/extension,
  size guard, then run extraction pipeline.
- New: `POST /documents/{id}/re-extract` (admin/PM) — re-run after
  parser upgrades or after LLM key added.
- New: `PATCH /documents/{id}/extracted-data` — user manual correction;
  marks `source=user_edited`.

### 1.3 Frontend (~45 min)
- New types: `PenaltyClause`, `KeyDate`, extended `ExtractedContractData`
- `api.subcontractors.documents.reExtract(docId)` + `.updateExtracted(...)`
- New component `<ExtractedDataPreview>`:
  - Source badge (Regex / LLM / LLM mock / User edited)
  - Confidence pill
  - Summary line
  - Key/value grid (editable in edit mode)
  - Penalty clauses list (red border)
  - Key dates list
  - Risk flags chips
  - Yellow banner when source=llm_mock with API key reminder
  - Re-extract + Edit/Save actions
- Document table row clickable → expandable inline `<ExtractedDataPreview>`
- Bot icon when `extracted_data` present, FileText icon otherwise.

## FAZ 3 - Insight Generator Extension (~1.5 hours)

### 3.1 Backend (~45 min)
- Extend `insight_generator.py` (no rewrite):
  - Per-contract pace projection (`category=schedule`)
  - Average payment delay analysis (`category=financial`)
  - Mock LLM commentary stub when `risk_score >= 30` (`source=llm_mock`)
- New file `app/services/insights_cache.py`:
  - In-memory dict, TTL=10 min, `get/set/invalidate/clear_all/stats`
- `AIInsight` schema extended with optional category, title, body, action,
  source fields (backwards-compat).
- `/ai-insights` endpoint:
  - Cache lookup at start; cache write before return
  - `?force_refresh=true` query param bypasses cache

### 3.2 Frontend (~45 min)
- Extended `AIInsight` type with optional fields
- `api.subcontractors.aiInsights(subId, forceRefresh=false)`
- New component `<SubcontractorInsightsCard>`:
  - Severity-sorted list (critical → warning → info)
  - Category filter chips with counts (financial / schedule / risk /
    performance / all)
  - Refresh button → calls force_refresh
  - Per-row source badges (LLM, mock)
  - Action callout
  - Mock-banner footer when any insight has `source=llm_mock`
- Replaces inline insights tab markup on subcontractor detail page.

## Risks + mitigations

- **Sandbox mount truncation:** Files >~12KB read from bash get cut off,
  causing python errors despite Edit tool writing correct content. Mitigation:
  use Read tool for verification, defer commits to host machine.
- **No real PDF:** Mock LLM path validated by inspection; real PDF
  pipeline validated only when key added (Day 12).
- **Confidence overstatement:** Insufficient data flag is honest, but Q1-Q4
  factors with <12mo data are statistical noise. Frontend warning badge
  required to keep user informed.

## Definition of done

- New endpoints: `/cashflow-forecast`, `/documents/{id}/re-extract`,
  `/documents/{id}/extracted-data`, `?force_refresh=true` on `/ai-insights`.
- Three new frontend components: CashFlowForecastChart, ExtractedDataPreview,
  SubcontractorInsightsCard.
- All schema additions backwards-compat (optional fields).
- Old endpoints + schemas untouched.
- Sprint log + roadmap updated.
- Day 12 carry-over list explicit (LLM key, real PDFs, cache invalidation).
