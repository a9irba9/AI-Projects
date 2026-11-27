import pytest
from app.extensions import db
from app.models.document import Document, DocumentPage
from app.models.extracted_information import ExtractedInformation
from app.services.information_extractor import extract_structured_info
from app.services.llm_provider import (
    LLMConfigurationError,
    LLMProvider,
    LLMProviderError,
    get_llm_provider,
)


class MockLLMProvider(LLMProvider):
    def generate_text(self, prompt: str, system_instruction=None) -> str:
        return "Mocked response"

    def generate_json(self, prompt: str, system_instruction=None) -> dict:
        return {
            "document_type": "Invoice",
            "supplier_name": "Acme Steel Corp",
            "document_number": "INV-001",
            "invoice_number": "INV-001",
            "purchase_order_number": None,
            "document_date": "2026-11-01",
            "due_date": "2026-12-01",
            "currency": "USD",
            "total_amount": "$1,250.50",
            "tax_amount": "125.05",
            "customer_name": "Global Tech KK",
            "supplier_contact": "billing@acmesteel.example",
            "products_or_services": ["Stainless Steel Sheets"],
            "important_terms": "Net 30",
        }

    def embed_texts(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class FailingLLMProvider(LLMProvider):
    def generate_text(self, prompt: str, system_instruction=None) -> str:
        raise LLMProviderError("API quota exceeded")

    def generate_json(self, prompt: str, system_instruction=None) -> dict:
        raise LLMProviderError("API quota exceeded")

    def embed_texts(self, texts):
        raise LLMProviderError("API quota exceeded")


def test_missing_api_credentials(app):
    """Verify missing GEMINI_API_KEY raises LLMConfigurationError."""
    with app.app_context():
        app.config["GEMINI_API_KEY"] = ""
        with pytest.raises(LLMConfigurationError):
            get_llm_provider()


def test_structured_extraction_validation(app):
    """Verify structured extraction normalizes numbers, nulls, and saves to DB."""
    with app.app_context():
        doc = Document(
            original_filename="inv1.pdf",
            stored_filename="uuid_inv1.pdf",
            file_hash="hash_m3_1",
            file_size=500,
            processing_status="completed",
            extraction_status="completed",
        )
        db.session.add(doc)
        db.session.flush()
        db.session.add(
            DocumentPage(
                document_id=doc.id,
                page_number=1,
                extracted_text="Invoice INV-001 Total: $1,250.50",
            )
        )
        db.session.commit()

        result = extract_structured_info(doc, MockLLMProvider())
        assert result["total_amount"] == "1250.50"
        assert result["tax_amount"] == "125.05"
        assert result["purchase_order_number"] is None
        assert doc.document_type == "invoice"

        saved = ExtractedInformation.query.filter_by(
            document_id=doc.id, field_name="total_amount"
        ).first()
        assert saved is not None
        assert saved.field_value == "1250.50"


def test_llm_api_failure_handling(app):
    """Verify LLMProviderError propagates cleanly on API failure."""
    with app.app_context():
        doc = Document(
            original_filename="inv_fail.pdf",
            stored_filename="uuid_inv_fail.pdf",
            file_hash="hash_m3_fail",
            file_size=500,
            processing_status="completed",
            extraction_status="completed",
        )
        db.session.add(doc)
        db.session.flush()
        db.session.add(
            DocumentPage(document_id=doc.id, page_number=1, extracted_text="Sample")
        )
        db.session.commit()

        with pytest.raises(LLMProviderError):
            extract_structured_info(doc, FailingLLMProvider())
