"""Regression: extracted_data is stored as a JSON string in the DB.

ContractDocumentResponse.model_validate(orm_obj) must parse it instead of
raising a ResponseValidationError (which surfaced to browsers as a
CORS-less 500 / "Failed to fetch" on upload + list endpoints)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas.subcontractor import ContractDocumentResponse, DocumentType


def _doc(extracted):
    return SimpleNamespace(
        id=1,
        contract_id=8,
        file_name="dogovor.md",
        file_size=123,
        mime_type="text/markdown",
        file_type=DocumentType.CONTRACT,
        version=1,
        extracted_data=extracted,
        uploaded_by=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestExtractedDataParsing:
    def test_json_string_is_parsed(self):
        resp = ContractDocumentResponse.model_validate(_doc('{"contract_amount": "100", "source": "mock"}'))
        assert resp.extracted_data == {"contract_amount": "100", "source": "mock"}

    def test_none_stays_none(self):
        assert ContractDocumentResponse.model_validate(_doc(None)).extracted_data is None

    def test_invalid_json_becomes_none(self):
        assert ContractDocumentResponse.model_validate(_doc("not-json{")).extracted_data is None

    def test_non_dict_json_becomes_none(self):
        assert ContractDocumentResponse.model_validate(_doc("[1,2,3]")).extracted_data is None

    def test_dict_passthrough(self):
        resp = ContractDocumentResponse.model_validate(_doc({"a": 1}))
        assert resp.extracted_data == {"a": 1}
