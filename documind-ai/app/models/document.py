from datetime import datetime, timezone
from app.extensions import db


class Document(db.Model):
    """Represents an uploaded business document and its processing state."""

    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    file_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    document_type = db.Column(db.String(64), nullable=True, index=True)
    upload_timestamp = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    processing_status = db.Column(
        db.String(32), nullable=False, default="pending", index=True
    )
    extraction_status = db.Column(db.String(32), nullable=False, default="pending")
    error_message = db.Column(db.Text, nullable=True)

    pages = db.relationship(
        "DocumentPage",
        backref="document",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="DocumentPage.page_number",
    )
    extracted_fields = db.relationship(
        "ExtractedInformation",
        backref="document",
        lazy=True,
        cascade="all, delete-orphan",
    )
    chunks = db.relationship(
        "DocumentChunk",
        backref="document",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "document_type": self.document_type,
            "upload_timestamp": self.upload_timestamp.isoformat(),
            "processing_status": self.processing_status,
            "extraction_status": self.extraction_status,
            "error_message": self.error_message,
            "page_count": len(self.pages),
        }


class DocumentPage(db.Model):
    """Stores extracted text for a single page of a document."""

    __tablename__ = "document_pages"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number = db.Column(db.Integer, nullable=False)
    extracted_text = db.Column(db.Text, nullable=False, default="")

    __table_args__ = (
        db.UniqueConstraint("document_id", "page_number", name="uq_doc_page"),
    )


class DocumentChunk(db.Model):
    """Stores text chunks used for semantic retrieval."""

    __tablename__ = "document_chunks"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number = db.Column(db.Integer, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
