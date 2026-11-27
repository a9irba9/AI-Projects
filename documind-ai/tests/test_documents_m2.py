import io
import fitz
from app.models.document import Document


def _make_synthetic_pdf(text: str = "Invoice INV-001\nTotal Amount: $1,250.00\nDue Date: 2026-12-15") -> bytes:
    """Create a synthetic single-page PDF in memory using PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_upload_and_extract_pdf(client, app, tmp_path):
    """Verify valid PDF upload extracts text and stores Document + DocumentPage."""
    app.config["UPLOAD_FOLDER"] = tmp_path
    pdf_bytes = _make_synthetic_pdf()

    res = client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(pdf_bytes), "invoice_001.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"invoice_001.pdf" in res.data
    assert b"INV-001" in res.data

    with app.app_context():
        doc = Document.query.filter_by(original_filename="invoice_001.pdf").first()
        assert doc is not None
        assert doc.processing_status == "completed"
        assert len(doc.pages) == 1


def test_reject_unsupported_file(client):
    """Verify non-PDF files are rejected safely."""
    res = client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(b"hello world"), "notes.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Unsupported file type" in res.data


def test_reject_fake_pdf_header(client):
    """Verify files with .pdf extension but invalid magic bytes are rejected."""
    res = client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(b"not a real pdf"), "fake.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Invalid PDF file" in res.data


def test_duplicate_document_detection(client, app, tmp_path):
    """Verify uploading the same PDF twice is detected via SHA-256 hash."""
    app.config["UPLOAD_FOLDER"] = tmp_path
    pdf_bytes = _make_synthetic_pdf("Unique Invoice INV-999 for duplicate test")

    client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(pdf_bytes), "dup1.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    res2 = client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(pdf_bytes), "dup2.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert res2.status_code == 200
    assert b"Duplicate document detected" in res2.data

    with app.app_context():
        assert Document.query.count() == 1


def test_delete_document(client, app, tmp_path):
    """Verify deleting a document removes both DB record and file on disk."""
    app.config["UPLOAD_FOLDER"] = tmp_path
    pdf_bytes = _make_synthetic_pdf("Document to delete")

    client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(pdf_bytes), "to_delete.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    with app.app_context():
        doc = Document.query.filter_by(original_filename="to_delete.pdf").first()
        doc_id = doc.id

    res = client.post(f"/documents/{doc_id}/delete", follow_redirects=True)
    assert res.status_code == 200
    assert b"Deleted" in res.data

    with app.app_context():
        assert Document.query.count() == 0
