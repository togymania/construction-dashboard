"""Pydantic schemas for the LedgerEntry domain.

Three groups:
  1. CRUD: LedgerEntryRead, LedgerEntryUpdate
  2. Import preview: ImportPreview + nested CompanyMatchProposal/ParseError
  3. Import commit: ImportCommitRequest, ImportResult
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- CRUD ----------


class LedgerEntryRead(BaseModel):
    """A ledger entry as returned by the API."""

    id: int
    entry_date: date
    description: str | None
    company_name: str | None
    kod: str | None
    account: str | None
    amount: Decimal
    entry_type: str
    budget_code: str | None
    subcontractor_id: int | None
    subcontractor_name: str | None
    contract_id: int | None
    contract_number: str | None
    source_filename: str | None
    source_row: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LedgerEntryUpdate(BaseModel):
    """Manual patch payload — only budget_code, subcontractor_id and contract_id are user-editable."""

    budget_code: str | None = Field(None, max_length=50)
    contract_id: int | None = None
    subcontractor_id: int | None = None


class LedgerBulkAssignRequest(BaseModel):
    """Apply a budget_code and/or subcontractor_id to many ledger entries in one shot.

    At least one of budget_code / subcontractor_id must be provided. If both are
    given, both are applied. `entry_ids` is required and must not be empty.

    Setting a field to null is allowed and intentionally clears that assignment
    (e.g. {"subcontractor_id": null} unlinks the chosen rows).
    """

    entry_ids: list[int] = Field(..., min_length=1, max_length=5000)
    budget_code: str | None = Field(None, max_length=50)
    subcontractor_id: int | None = None
    set_budget_code: bool = False
    set_subcontractor_id: bool = False


class LedgerBulkAssignResponse(BaseModel):
    """Summary of a bulk-assign run."""

    updated: int
    skipped: int
    not_found: list[int] = Field(default_factory=list)


class LedgerListResponse(BaseModel):
    """Paginated list response."""

    items: list[LedgerEntryRead]
    total: int
    limit: int
    offset: int


# ---------- Import preview ----------


class ParseError(BaseModel):
    """A row that failed to parse from the source Excel."""

    source_row: int
    reason: str


class CompanyMatchProposal(BaseModel):
    """One unique company name + best matching subcontractor (if any)."""

    company_name: str
    occurrences: int
    candidate_id: int | None
    candidate_name: str | None
    score: float
    high_confidence: bool


class ImportPreview(BaseModel):
    """Preview returned after parsing the uploaded Excel.

    The `import_token` references the parsed-rows cache server-side and must
    be passed back to /commit to finalize the import.
    """

    import_token: str
    filename: str
    total_rows_parsed: int
    income_count: int
    expense_count: int
    income_total: Decimal
    expense_total: Decimal
    duplicates_in_file: int
    duplicates_in_db: int
    rows_to_import: int
    parse_errors: list[ParseError]
    match_proposals: list[CompanyMatchProposal]
    unmatched_companies_count: int


# ---------- Import commit ----------


class AcceptedMatch(BaseModel):
    """A single company-name → subcontractor decision the user made in the wizard.

    `subcontractor_id=None` is allowed and means "I reviewed this and chose not to
    link to any subcontractor" (e.g. a bank or supplier). Companies omitted from
    the request are also treated as unlinked.
    """

    company_name: str
    subcontractor_id: int | None = None


class ImportCommitRequest(BaseModel):
    """Body for POST /commit.

    Only the import_token is required. accepted_matches may be empty if the user
    chose to skip every proposal.
    """

    import_token: str
    accepted_matches: list[AcceptedMatch] = []


class ImportResult(BaseModel):
    """Outcome of a successful commit."""

    created_count: int
    skipped_duplicate_count: int
    linked_to_subcontractor_count: int
    error_count: int
    errors: list[ParseError]


# ---------- Stats / KPI for the page header ----------


class LedgerStats(BaseModel):
    """Top-of-page KPI block."""

    total_income: Decimal
    total_expense: Decimal
    net: Decimal
    entry_count: int
    pending_budget_code_count: int  # rows with budget_code IS NULL
    unmatched_subcontractor_count: int  # rows with subcontractor_id IS NULL


# ---------- Subcontractor-scoped payment listing ----------


class SubcontractorPaymentEntry(BaseModel):
    """A ledger entry surfaced under a subcontractor's "Ödemeler" tab."""

    id: int
    entry_date: date
    description: str | None
    amount: Decimal
    entry_type: Literal["income", "expense"]
    kod: str | None
    contract_id: int | None
    contract_number: str | None
    source_row: int | None

    model_config = ConfigDict(from_attributes=True)
