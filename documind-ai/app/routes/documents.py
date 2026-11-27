from pathlib import Path
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from app.extensions import db
from app.models.document import Document, DocumentPage
from app.models.extracted_information import ExtractedInformation
from app.services.information_extractor import extract_structured_info
from app.services.llm_provider import (
    LLMConfigurationError,
    LLMProviderError,
    get_llm_provider,
)
from app.services.pdf_extractor import extract_text_from_pdf
from app.services.rag_service import index_document
from app.services.vector_store import VectorStore
from app.utils.validators import (
    allowed_file,
    compute_file_hash,
    generate_stored_filename,
    is_valid_pdf_header,
)

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


@documents_bp.route("/")
def list_documents():
    """List and optionally search uploaded documents."""
    query_text = request.args.get("q", "").strip()
    query = Document.query
    if query_text:
        query = query.filter(Document.original_filename.ilike(f"%{query_text}%"))
    docs = query.order_by(Document.upload_timestamp.desc()).all()
    return render_template("documents.html", documents=docs, query_text=query_text)


@documents_bp.route("/upload", methods=["POST"])
def upload_document():
    """Validate, store, deduplicate, and extract text from an uploaded PDF."""
    if "file" not in request.files:
        flash("No file part in the request.", "danger")
        return redirect(url_for("documents.list_documents"))

    files = [f for f in request.files.getlist("file") if f and f.filename != ""]
    if not files:
        flash("No file selected.", "warning")
        return redirect(url_for("documents.list_documents"))

    last_doc_id = None
    for file in files:
        if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            flash(f"Unsupported file type '{file.filename}'. Only PDF files are allowed.", "danger")
            continue

        if not is_valid_pdf_header(file.stream):
            flash(f"Invalid PDF file '{file.filename}' (missing %PDF- header).", "danger")
            continue

        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        stored_filename = generate_stored_filename(file.filename)
        dest_path = upload_folder / stored_filename
        file.save(dest_path)

        file_hash = compute_file_hash(dest_path)
        existing = Document.query.filter_by(file_hash=file_hash).first()
        if existing:
            dest_path.unlink(missing_ok=True)
            flash(
                f"Duplicate document detected: '{existing.original_filename}' is already uploaded.",
                "warning",
            )
            last_doc_id = existing.id
            continue

        doc = Document(
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_hash=file_hash,
            file_size=dest_path.stat().st_size,
            processing_status="processing",
            extraction_status="pending",
        )
        db.session.add(doc)
        db.session.commit()
        last_doc_id = doc.id

        # Extract text page by page
        result = extract_text_from_pdf(dest_path)
        doc.extraction_status = result.extraction_status
        if result.success:
            for page in result.pages:
                db.session.add(
                    DocumentPage(
                        document_id=doc.id,
                        page_number=page.page_number,
                        extracted_text=page.text,
                    )
                )
            doc.processing_status = "completed"
            db.session.commit()
            try:
                provider = get_llm_provider()
                extract_structured_info(doc, provider)
                vector_store = VectorStore(current_app.config["VECTOR_INDEX_FOLDER"])
                index_document(
                    doc,
                    provider,
                    vector_store,
                    chunk_size=current_app.config.get("CHUNK_SIZE", 1000),
                    overlap=current_app.config.get("CHUNK_OVERLAP", 200),
                )
                flash(
                    f"Uploaded, extracted text ({len(result.pages)} pages), indexed, and extracted structured fields for '{doc.original_filename}'.",
                    "success",
                )
            except LLMConfigurationError:
                flash(
                    f"Uploaded and extracted text ({len(result.pages)} pages) for '{doc.original_filename}'. Configure GEMINI_API_KEY in .env for AI field extraction.",
                    "info",
                )
            except LLMProviderError as exc:
                flash(
                    f"Text extracted for '{doc.original_filename}', but AI field extraction failed: {exc}",
                    "warning",
                )
        else:
            doc.processing_status = "failed"
            doc.error_message = result.error_message
            db.session.commit()
            flash(f"Text extraction failed for '{doc.original_filename}': {result.error_message}", "danger")

    if len(files) == 1 and last_doc_id is not None:
        return redirect(url_for("documents.document_detail", doc_id=last_doc_id))
    return redirect(url_for("documents.list_documents"))


@documents_bp.route("/<int:doc_id>")
def document_detail(doc_id: int):
    """Display document metadata, extracted text by page, and extracted fields."""
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("Document not found.", "danger")
        return redirect(url_for("documents.list_documents"))
    return render_template("document_detail.html", doc=doc)


@documents_bp.route("/<int:doc_id>/delete", methods=["POST"])
def delete_document(doc_id: int):
    """Safely delete a document record and its stored PDF file."""
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("Document not found.", "danger")
        return redirect(url_for("documents.list_documents"))

    file_path = Path(current_app.config["UPLOAD_FOLDER"]) / doc.stored_filename
    file_path.unlink(missing_ok=True)

    vector_store = VectorStore(current_app.config["VECTOR_INDEX_FOLDER"])
    vector_store.delete_document_vectors(doc.id)

    filename = doc.original_filename
    db.session.delete(doc)
    db.session.commit()
    flash(f"Deleted '{filename}'.", "info")
    return redirect(url_for("documents.list_documents"))


@documents_bp.route("/<int:doc_id>/extract", methods=["POST"])
def extract_fields(doc_id: int):
    """Run or re-run LLM structured information extraction on a document."""
    doc = db.session.get(Document, doc_id)
    if not doc or not doc.pages:
        flash("Document has no extracted text to analyze.", "warning")
        return redirect(url_for("documents.list_documents"))

    try:
        provider = get_llm_provider()
        extract_structured_info(doc, provider)
        flash("Structured information extracted successfully.", "success")
    except (LLMConfigurationError, LLMProviderError) as exc:
        flash(f"Extraction failed: {exc}", "danger")

    return redirect(url_for("documents.document_detail", doc_id=doc.id))


@documents_bp.route("/<int:doc_id>/fields/update", methods=["POST"])
def update_fields(doc_id: int):
    """Allow manual correction of extracted business fields."""
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("Document not found.", "danger")
        return redirect(url_for("documents.list_documents"))

    for field in doc.extracted_fields:
        new_val = request.form.get(f"field_{field.id}")
        if new_val is not None:
            field.field_value = new_val.strip() or None
            if field.field_name == "document_type" and field.field_value:
                doc.document_type = field.field_value.lower()[:64]

    db.session.commit()
    flash("Extracted fields updated.", "success")
    return redirect(url_for("documents.document_detail", doc_id=doc.id))


@documents_bp.route("/compare", methods=["GET", "POST"])
def compare_documents():
    """Compare two uploaded documents side-by-side."""
    all_docs = Document.query.order_by(Document.upload_timestamp.desc()).all()
    doc1 = doc2 = None
    fields1 = {}
    fields2 = {}
    ai_summary = None

    doc1_id = request.values.get("doc1_id", type=int)
    doc2_id = request.values.get("doc2_id", type=int)

    if doc1_id and doc2_id:
        doc1 = db.session.get(Document, doc1_id)
        doc2 = db.session.get(Document, doc2_id)
        if doc1 and doc2:
            fields1 = {f.field_name: f.field_value for f in doc1.extracted_fields}
            fields2 = {f.field_name: f.field_value for f in doc2.extracted_fields}
            if request.method == "POST":
                try:
                    provider = get_llm_provider()
                    prompt = (
                        f"Compare these two business documents concisely in bullet points:\n"
                        f"Document 1 ({doc1.original_filename}): {fields1}\n"
                        f"Document 2 ({doc2.original_filename}): {fields2}"
                    )
                    ai_summary = provider.generate_text(prompt)
                except (LLMConfigurationError, LLMProviderError) as exc:
                    flash(f"AI comparison summary unavailable: {exc}", "warning")

    compare_keys = [
        "document_type",
        "supplier_name",
        "invoice_number",
        "document_date",
        "due_date",
        "currency",
        "total_amount",
        "tax_amount",
        "important_terms",
    ]
    return render_template(
        "compare.html",
        all_docs=all_docs,
        doc1=doc1,
        doc2=doc2,
        fields1=fields1,
        fields2=fields2,
        compare_keys=compare_keys,
        ai_summary=ai_summary,
    )
