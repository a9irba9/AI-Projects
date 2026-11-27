from typing import List
from app.extensions import db
from app.models.document import Document, DocumentChunk


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping character chunks."""
    if not text or not text.strip():
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    chunks: List[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_len:
            break
        start = end - overlap
    return chunks


def create_document_chunks(
    doc: Document, chunk_size: int = 1000, overlap: int = 200
) -> List[DocumentChunk]:
    """Generate and persist DocumentChunk rows for all pages of a Document."""
    DocumentChunk.query.filter_by(document_id=doc.id).delete()

    created: List[DocumentChunk] = []
    idx = 0
    for page in doc.pages:
        for text_chunk in chunk_text(page.extracted_text, chunk_size, overlap):
            chunk = DocumentChunk(
                document_id=doc.id,
                page_number=page.page_number,
                chunk_index=idx,
                chunk_text=text_chunk,
            )
            db.session.add(chunk)
            created.append(chunk)
            idx += 1

    db.session.commit()
    return created
