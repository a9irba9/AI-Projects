import csv
import io
from flask import Blueprint, Response, current_app, render_template
from app.models.document import Document
from app.services.ocr_service import is_ocr_available

exports_bp = Blueprint("exports", __name__, url_prefix="/exports")


def _build_extracted_rows() -> list[dict]:
    docs = Document.query.order_by(Document.upload_timestamp.desc()).all()
    rows = []
    for doc in docs:
        fields = {f.field_name: f.field_value for f in doc.extracted_fields}
        rows.append(
            {
                "document_id": doc.id,
                "document_name": doc.original_filename,
                "document_type": fields.get("document_type") or doc.document_type or "",
                "supplier": fields.get("supplier_name") or "",
                "invoice_number": fields.get("invoice_number") or fields.get("document_number") or "",
                "document_date": fields.get("document_date") or "",
                "due_date": fields.get("due_date") or "",
                "currency": fields.get("currency") or "",
                "total_amount": fields.get("total_amount") or "",
                "processing_status": doc.processing_status,
            }
        )
    return rows


@exports_bp.route("/extracted")
def extracted_data():
    """Render the Extracted Data overview table."""
    rows = _build_extracted_rows()
    return render_template("extracted_data.html", rows=rows)


@exports_bp.route("/csv")
def export_csv():
    """Export extracted document information as a properly escaped CSV file."""
    rows = _build_extracted_rows()
    output = io.StringIO()
    fieldnames = [
        "document_name",
        "document_type",
        "supplier",
        "invoice_number",
        "document_date",
        "due_date",
        "currency",
        "total_amount",
        "processing_status",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=documind_extracted_data.csv"},
    )


@exports_bp.route("/settings")
def settings():
    """Render system configuration and dependency status."""
    api_key = current_app.config.get("GEMINI_API_KEY", "")
    key_configured = bool(api_key and api_key != "your-gemini-api-key-here")
    config_info = {
        "llm_provider": current_app.config.get("LLM_PROVIDER", "gemini"),
        "gemini_model": current_app.config.get("GEMINI_MODEL"),
        "embedding_model": current_app.config.get("GEMINI_EMBEDDING_MODEL"),
        "key_configured": key_configured,
        "ocr_available": is_ocr_available(),
        "chunk_size": current_app.config.get("CHUNK_SIZE"),
        "chunk_overlap": current_app.config.get("CHUNK_OVERLAP"),
        "top_k": current_app.config.get("TOP_K_RESULTS"),
    }
    return render_template("settings.html", config_info=config_info)
