from app.extensions import db
from app.models.document import Document, DocumentPage
from app.services.embedding_service import chunk_text
from app.services.llm_provider import LLMProvider
from app.services.rag_service import answer_question, index_document
from app.services.vector_store import VectorStore


class MockRAGProvider(LLMProvider):
    def generate_text(self, prompt: str, system_instruction=None) -> str:
        return "The total amount of INV-001 is $1,250.50 (invoice_001.pdf, Page 1)."

    def generate_json(self, prompt: str, system_instruction=None) -> dict:
        return {}

    def embed_texts(self, texts):
        # Deterministic simple 4D embeddings based on keyword presence
        vectors = []
        for t in texts:
            tl = t.lower()
            vectors.append([
                1.0 if "invoice" in tl or "total" in tl else 0.1,
                1.0 if "steel" in tl else 0.1,
                1.0 if "due" in tl or "payment" in tl else 0.1,
                0.5,
            ])
        return vectors


def test_chunk_generation():
    """Verify chunk_text splits text with configurable size and overlap."""
    text = "A" * 250
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) == 3
    assert len(chunks[0]) == 100


def test_rag_indexing_and_source_attribution(app, tmp_path):
    """Verify indexing, semantic retrieval, and source attribution."""
    with app.app_context():
        doc = Document(
            original_filename="invoice_001.pdf",
            stored_filename="uuid_inv001.pdf",
            file_hash="hash_rag_1",
            file_size=500,
            processing_status="completed",
            extraction_status="completed",
        )
        db.session.add(doc)
        db.session.flush()
        db.session.add(
            DocumentPage(
                document_id=doc.id,
                page_number=1,
                extracted_text="Invoice INV-001. Total amount: $1,250.50. Payment due: 2026-12-01.",
            )
        )
        db.session.commit()

        vs = VectorStore(tmp_path)
        provider = MockRAGProvider()
        count = index_document(doc, provider, vs, chunk_size=500, overlap=50)
        assert count == 1

        res = answer_question("What is the total amount?", provider, vs, top_k=3)
        assert "1,250.50" in res["answer"]
        assert len(res["sources"]) == 1
        assert res["sources"][0]["document_name"] == "invoice_001.pdf"
        assert res["sources"][0]["page_number"] == 1


def test_rag_empty_index_response(app, tmp_path):
    """Verify RAG explicitly states when no documents are indexed."""
    with app.app_context():
        vs = VectorStore(tmp_path)
        provider = MockRAGProvider()
        res = answer_question("What is the total amount?", provider, vs)
        assert "do not contain enough information" in res["answer"].lower()
        assert res["sources"] == []
