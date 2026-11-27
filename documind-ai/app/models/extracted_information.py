from app.extensions import db


class ExtractedInformation(db.Model):
    """Stores structured business fields extracted from a document."""

    __tablename__ = "extracted_information"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name = db.Column(db.String(64), nullable=False, index=True)
    field_value = db.Column(db.Text, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    source_page = db.Column(db.Integer, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "field_name": self.field_name,
            "field_value": self.field_value,
            "confidence": self.confidence,
            "source_page": self.source_page,
        }
