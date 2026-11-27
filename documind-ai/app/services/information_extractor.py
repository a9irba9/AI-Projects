import json
import logging
from typing import Any, Optional
from app.extensions import db
from app.models.document import Document
from app.models.extracted_information import ExtractedInformation
from app.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

EXTRACTION_FIELDS = [
    "document_type",
    "supplier_name",
    "document_number",
    "invoice_number",
    "purchase_order_number",
    "document_date",
    "due_date",
    "currency",
    "total_amount",
    "tax_amount",
    "customer_name",
    "supplier_contact",
    "products_or_services",
    "important_terms",
]

NUMERIC_FIELDS = {"total_amount", "tax_amount"}

SYSTEM_PROMPT = (
    "You are a precise business document data extraction assistant. "
    "Extract only information explicitly present in the provided document text. "
    "Never invent or guess missing values; use null for any field not found."
)


def _normalize_numeric(value: Any) -> Optional[str]:
    """Validate and normalize numeric fields (e.g. total_amount, tax_amount)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    cleaned = str(value).replace(",", "").strip()
    for prefix in ("$", "€", "£", "¥", "USD", "JPY", "EUR"):
        cleaned = cleaned.replace(prefix, "").strip()
    try:
        num = float(cleaned)
        return f"{num:.2f}"
    except ValueError:
        return None


def extract_structured_info(doc: Document, provider: LLMProvider) -> dict[str, Any]:
    """
    Use the LLM provider to extract structured business fields from a Document's pages
    and persist them in ExtractedInformation.
    """
    full_text = "\n\n".join(
        f"--- Page {p.page_number} ---\n{p.extracted_text}" for p in doc.pages
    )
    prompt = (
        "Extract the following fields as a JSON object from the document text below. "
        "Use null for any missing field. For 'products_or_services', return a concise "
        "list of items or a summary string.\n\n"
        f"Fields: {', '.join(EXTRACTION_FIELDS)}\n\n"
        f"Document Text:\n{full_text[:25000]}"
    )

    raw_data = provider.generate_json(prompt, system_instruction=SYSTEM_PROMPT)

    # Clear previous extracted fields for this document
    ExtractedInformation.query.filter_by(document_id=doc.id).delete()

    normalized: dict[str, Any] = {}
    for field in EXTRACTION_FIELDS:
        val = raw_data.get(field)
        if field in NUMERIC_FIELDS:
            val_str = _normalize_numeric(val)
        elif isinstance(val, (list, dict)):
            val_str = json.dumps(val, ensure_ascii=False)
        elif val is not None:
            val_str = str(val).strip() or None
        else:
            val_str = None

        normalized[field] = val_str
        db.session.add(
            ExtractedInformation(
                document_id=doc.id,
                field_name=field,
                field_value=val_str,
                source_page=1 if doc.pages else None,
            )
        )

    if normalized.get("document_type"):
        doc.document_type = str(normalized["document_type"]).lower()[:64]

    db.session.commit()
    return normalized
