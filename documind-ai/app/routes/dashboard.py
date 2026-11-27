from flask import Blueprint, render_template, jsonify
from sqlalchemy import func
from app.extensions import db
from app.models.document import Document

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Render the main business dashboard."""
    total_docs = Document.query.count()
    processed_docs = Document.query.filter_by(processing_status="completed").count()
    failed_docs = Document.query.filter_by(processing_status="failed").count()
    total_invoices = Document.query.filter_by(document_type="invoice").count()
    recent_docs = (
        Document.query.order_by(Document.upload_timestamp.desc()).limit(5).all()
    )

    stats = {
        "total_docs": total_docs,
        "processed_docs": processed_docs,
        "failed_docs": failed_docs,
        "total_invoices": total_invoices,
    }

    cat_rows = (
        db.session.query(Document.document_type, func.count(Document.id))
        .group_by(Document.document_type)
        .all()
    )
    category_counts = {
        (cat or "unclassified").title(): count for cat, count in cat_rows
    }
    status_counts = {
        "Completed": processed_docs,
        "Failed": failed_docs,
        "Pending/Other": max(0, total_docs - processed_docs - failed_docs),
    }

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_docs=recent_docs,
        category_counts=category_counts,
        status_counts=status_counts,
    )


@dashboard_bp.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "DocuMind AI"})
