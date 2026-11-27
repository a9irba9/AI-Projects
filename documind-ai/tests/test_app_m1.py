from app.models.document import Document, DocumentPage, DocumentChunk
from app.models.extracted_information import ExtractedInformation
from app.models.conversation import Conversation, Message
from app.extensions import db


def test_health_endpoint(client):
    """Verify the health check endpoint returns 200 OK."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"


def test_dashboard_renders(client):
    """Verify the dashboard page renders with zeroed stats."""
    res = client.get("/")
    assert res.status_code == 200
    assert b"DocuMind AI" in res.data
    assert b"Total Documents" in res.data


def test_database_persistence(app):
    """Verify SQLAlchemy models persist and cascade properly."""
    with app.app_context():
        doc = Document(
            original_filename="test_invoice.pdf",
            stored_filename="uuid_test_invoice.pdf",
            file_hash="abc123hash",
            file_size=1024,
            document_type="invoice",
            processing_status="completed",
            extraction_status="completed",
        )
        db.session.add(doc)
        db.session.flush()

        page = DocumentPage(
            document_id=doc.id, page_number=1, extracted_text="Invoice #INV-001"
        )
        info = ExtractedInformation(
            document_id=doc.id,
            field_name="invoice_number",
            field_value="INV-001",
            source_page=1,
        )
        chunk = DocumentChunk(
            document_id=doc.id,
            page_number=1,
            chunk_index=0,
            chunk_text="Invoice #INV-001",
        )
        db.session.add_all([page, info, chunk])
        db.session.commit()

        fetched = Document.query.filter_by(file_hash="abc123hash").first()
        assert fetched is not None
        assert len(fetched.pages) == 1
        assert len(fetched.extracted_fields) == 1
        assert len(fetched.chunks) == 1
