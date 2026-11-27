from typing import Any, List
from app.models.document import Document
from app.services.embedding_service import create_document_chunks
from app.services.llm_provider import LLMProvider
from app.services.vector_store import VectorStore

RAG_SYSTEM_PROMPT = (
    "You are DocuMind AI, an enterprise document intelligence assistant. "
    "Answer the user's question ONLY using the provided document excerpts. "
    "If the excerpts do not contain enough information to answer, explicitly state: "
    "'The uploaded documents do not contain enough information to answer this question.' "
    "Always cite the document name and page number when referencing facts."
)


def index_document(
    doc: Document,
    provider: LLMProvider,
    vector_store: VectorStore,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> int:
    """Chunk, embed, and index a Document into the VectorStore."""
    chunks = create_document_chunks(doc, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return 0

    texts = [c.chunk_text for c in chunks]
    vectors = provider.embed_texts(texts)

    vector_store.delete_document_vectors(doc.id)
    metadatas = [
        {
            "document_id": doc.id,
            "document_name": doc.original_filename,
            "page_number": c.page_number,
            "chunk_index": c.chunk_index,
            "chunk_text": c.chunk_text,
        }
        for c in chunks
    ]
    vector_store.add_vectors(vectors, metadatas)
    return len(chunks)


def answer_question(
    question: str,
    provider: LLMProvider,
    vector_store: VectorStore,
    top_k: int = 5,
    response_language: str = "Auto (match question)",
) -> dict[str, Any]:
    """Retrieve relevant chunks and generate a grounded answer with source attribution."""
    q_vectors = provider.embed_texts([question])
    if not q_vectors:
        return {
            "answer": "Unable to process your question.",
            "sources": [],
        }

    hits = vector_store.search(q_vectors[0], top_k=top_k)
    if not hits:
        return {
            "answer": "The uploaded documents do not contain enough information to answer this question.",
            "sources": [],
        }

    context_blocks: List[str] = []
    sources: List[dict[str, Any]] = []
    seen_sources = set()

    for hit in hits:
        doc_name = hit["document_name"]
        page_num = hit["page_number"]
        text = hit["chunk_text"]
        context_blocks.append(f"[Source: {doc_name}, Page {page_num}]\n{text}")

        key = (hit["document_id"], page_num)
        if key not in seen_sources:
            seen_sources.add(key)
            sources.append(
                {
                    "document_id": hit["document_id"],
                    "document_name": doc_name,
                    "page_number": page_num,
                    "excerpt": text[:240] + ("..." if len(text) > 240 else ""),
                }
            )

    lang_instruction = (
        f"Respond in {response_language}."
        if response_language and response_language != "Auto (match question)"
        else "Respond in the same language as the User Question."
    )
    prompt = (
        "Context Excerpts:\n"
        + "\n\n---\n\n".join(context_blocks)
        + f"\n\nUser Question: {question}\n\n"
        f"Provide a clear, concise answer grounded strictly in the context above. {lang_instruction}"
    )
    answer = provider.generate_text(prompt, system_instruction=RAG_SYSTEM_PROMPT)
    return {"answer": answer, "sources": sources}
