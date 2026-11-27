from app.extensions import db
from app.models.document import Document
from app.models.extracted_information import ExtractedInformation


def test_csv_export_escaping(client, app):
    """Verify CSV export properly escapes commas/quotes and includes expected headers."""
    with app.app_context():
        doc = Document(
            original_filename="inv_csv.pdf",
            stored_filename="uuid_inv_csv.pdf",
            file_hash="hash_csv_1",
            file_size=100,
            document_type="invoice",
            processing_status="completed",
            extraction_status="completed",
        )
        db.session.add(doc)
        db.session.flush()
        db.session.add(
            ExtractedInformation(
                document_id=doc.id,
                field_name="supplier_name",
                field_value='Acme, "Steel" Corp',
            )
        )
        db.session.add(
            ExtractedInformation(
                document_id=doc.id,
                field_name="total_amount",
                field_value="1100.00",
            )
        )
        db.session.commit()

    res = client.get("/exports/csv")
    assert res.status_code == 200
    assert "text/csv" in res.content_type
    csv_text = res.data.decode("utf-8")
    assert "document_name,document_type,supplier,invoice_number" in csv_text
    assert '"Acme, ""Steel"" Corp"' in csv_text
    assert "1100.00" in csv_text


def test_extracted_data_and_settings_pages(client):
    """Verify Extracted Data and Settings pages render cleanly."""
    assert client.get("/exports/extracted").status_code == 200
    assert client.get("/exports/settings").status_code == 200
