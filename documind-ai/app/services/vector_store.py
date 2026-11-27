import json
import logging
from pathlib import Path
from typing import Any, List
import faiss
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS-backed vector store with JSON metadata persistence."""

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "index.faiss"
        self.meta_path = self.index_dir / "metadata.json"
        self.index: faiss.IndexFlatIP | None = None
        self.metadata: List[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.index_path.exists() and self.meta_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            with open(self.meta_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
        else:
            self.index = None
            self.metadata = []

    def _save(self) -> None:
        if self.index is not None:
            faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (vectors / norms).astype("float32")

    def add_vectors(
        self, vectors: List[List[float]], metadatas: List[dict[str, Any]]
    ) -> None:
        if not vectors:
            return
        arr = self._normalize(np.array(vectors, dtype="float32"))
        dim = arr.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatIP(dim)
        self.index.add(arr)
        self.metadata.extend(metadatas)
        self._save()

    def search(
        self, query_vector: List[float], top_k: int = 5
    ) -> List[dict[str, Any]]:
        if self.index is None or self.index.ntotal == 0:
            return []
        q = self._normalize(np.array([query_vector], dtype="float32"))
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(q, k)

        results: List[dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            item = dict(self.metadata[idx])
            item["score"] = float(score)
            results.append(item)
        return results

    def delete_document_vectors(self, document_id: int) -> None:
        """Remove all vectors belonging to a document by rebuilding the index."""
        if self.index is None or not self.metadata:
            return
        keep_indices = [
            i for i, m in enumerate(self.metadata) if m.get("document_id") != document_id
        ]
        if len(keep_indices) == len(self.metadata):
            return

        if not keep_indices:
            self.index = None
            self.metadata = []
            if self.index_path.exists():
                self.index_path.unlink()
            self._save()
            return

        all_vectors = self.index.reconstruct_n(0, self.index.ntotal)
        kept_vectors = all_vectors[keep_indices]
        dim = kept_vectors.shape[1]
        new_index = faiss.IndexFlatIP(dim)
        new_index.add(kept_vectors)
        self.index = new_index
        self.metadata = [self.metadata[i] for i in keep_indices]
        self._save()
