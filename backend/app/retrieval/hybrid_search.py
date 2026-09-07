"""
Hybrid retrieval: combines dense (embedding/vector-store) and sparse
(BM25) results using min-max normalized weighted-sum fusion (a
simpler, more explainable alternative to Reciprocal Rank Fusion,
though we also expose RRF as the optional bonus reranking layer).

This module is the single entry point the Retrieval Agent calls —
it owns: running both searches, normalizing scores onto [0,1],
fusing them, applying role-based access filtering, and returning
chunks annotated with their source document for citation/attribution.
"""
from dataclasses import dataclass

from backend.app.retrieval.document_loader import Chunk, load_all_chunks
from backend.app.retrieval.embeddings import get_embedder
from backend.app.retrieval.sparse_search import SparseIndex
from backend.app.retrieval.vector_store import ACCESS_BY_ROLE, get_vector_store

DENSE_WEIGHT = 0.6
SPARSE_WEIGHT = 0.4


@dataclass
class RetrievedChunk:
    chunk: Chunk
    dense_score: float
    sparse_score: float
    hybrid_score: float


class HybridRetriever:
    """Lazily builds the indices once per process (documents are static
    for this POC; a production system would re-index on document change
    events instead of at every startup)."""

    _instance = None

    def __init__(self):
        self.chunks: list[Chunk] = load_all_chunks()
        self.embedder = get_embedder()
        self.sparse_index = SparseIndex(self.chunks)
        self.vector_store = get_vector_store()
        if self.chunks:
            texts = [c.text for c in self.chunks]
            vectors = self.embedder.embed(texts)
            self.vector_store.upsert(self.chunks, vectors)

    @classmethod
    def instance(cls) -> "HybridRetriever":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _normalize(scores: list[float]) -> list[float]:
        if not scores:
            return []
        lo, hi = min(scores), max(scores)
        if hi - lo < 1e-9:
            return [0.5 for _ in scores]
        return [(s - lo) / (hi - lo) for s in scores]

    def search(
        self,
        query: str,
        role: str,
        department_filter: str | None = None,
        document_type: str | None = None,
        top_k: int = 6,
    ) -> list[RetrievedChunk]:
        allowed_access = ACCESS_BY_ROLE.get(role, {"internal"})

        query_vec = self.embedder.embed_query(query) if hasattr(self.embedder, "embed_query") else self.embedder.embed([query])[0]
        dense_hits = self.vector_store.query(
            query_vec,
            top_k=top_k * 3,
            namespace=department_filter,
            allowed_access_levels=allowed_access,
            document_type=document_type,
        )
        sparse_hits = self.sparse_index.search(query, top_k=top_k * 3)
        sparse_hits = [
            (c, s) for c, s in sparse_hits
            if c.metadata.get("access_level") in allowed_access
            and (department_filter is None or c.metadata.get("department") == department_filter)
            and (document_type is None or c.metadata.get("document_type") == document_type)
        ]

        dense_by_id = {c.chunk_id: score for c, score in dense_hits}
        sparse_by_id = {c.chunk_id: score for c, score in sparse_hits}
        all_chunk_ids = set(dense_by_id) | set(sparse_by_id)
        chunk_lookup = {c.chunk_id: c for c, _ in dense_hits} | {c.chunk_id: c for c, _ in sparse_hits}

        dense_norm = dict(zip(dense_by_id.keys(), self._normalize(list(dense_by_id.values()))))
        sparse_norm = dict(zip(sparse_by_id.keys(), self._normalize(list(sparse_by_id.values()))))

        fused = []
        for cid in all_chunk_ids:
            d = dense_norm.get(cid, 0.0)
            s = sparse_norm.get(cid, 0.0)
            hybrid = DENSE_WEIGHT * d + SPARSE_WEIGHT * s
            fused.append(
                RetrievedChunk(
                    chunk=chunk_lookup[cid],
                    dense_score=float(d),
                    sparse_score=float(s),
                    hybrid_score=float(hybrid),
                )
            )

        fused.sort(key=lambda r: r.hybrid_score, reverse=True)
        return fused[:top_k]
