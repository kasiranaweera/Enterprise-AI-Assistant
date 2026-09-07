"""
Vector store abstraction: real Pinecone (namespaces + metadata filtering)
when PINECONE_API_KEY is set, else an in-memory numpy cosine-similarity
store with the identical interface. This lets the whole retrieval stack
(and the demo) run with zero paid services while still satisfying the
"use Pinecone" requirement when credentials are supplied.

Namespace strategy: one namespace per `department` (spec explicitly
lists "Namespaces" as a requirement). Metadata filtering additionally
restricts by `access_level` at query time based on the caller's role —
viewers only ever see access_level == "internal", analysts/admins can
see "internal" and "restricted".
"""
import numpy as np

from backend.app.config import get_settings
from backend.app.retrieval.document_loader import Chunk

settings = get_settings()

ACCESS_BY_ROLE = {
    "viewer": {"internal"},
    "analyst": {"internal", "restricted"},
    "administrator": {"internal", "restricted", "confidential"},
}


class LocalVectorStore:
    """Namespace-partitioned, numpy cosine-similarity in-memory index."""

    def __init__(self):
        self._namespaces: dict[str, list[tuple[Chunk, np.ndarray]]] = {}

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        for chunk, vec in zip(chunks, vectors):
            ns = chunk.metadata.get("department", "general")
            self._namespaces.setdefault(ns, []).append((chunk, vec))

    def query(
        self,
        query_vector: np.ndarray,
        top_k: int,
        namespace: str | None = None,
        allowed_access_levels: set[str] | None = None,
        document_type: str | None = None,
    ) -> list[tuple[Chunk, float]]:
        pool: list[tuple[Chunk, np.ndarray]] = []
        if namespace:
            pool = self._namespaces.get(namespace, [])
        else:
            for items in self._namespaces.values():
                pool.extend(items)

        results = []
        qn = query_vector / (np.linalg.norm(query_vector) + 1e-8)
        for chunk, vec in pool:
            if allowed_access_levels and chunk.metadata.get("access_level") not in allowed_access_levels:
                continue
            if document_type and chunk.metadata.get("document_type") != document_type:
                continue
            vn = vec / (np.linalg.norm(vec) + 1e-8)
            score = float(np.dot(qn, vn))
            results.append((chunk, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class PineconeVectorStore:
    """Thin wrapper around the real Pinecone SDK. Same `.query()` signature
    as LocalVectorStore so callers are agnostic to which backend is live."""

    def __init__(self):
        from pinecone import Pinecone, ServerlessSpec

        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        existing = [i.name for i in self._pc.list_indexes()]
        if settings.pinecone_index_name not in existing:
            self._pc.create_index(
                name=settings.pinecone_index_name,
                dimension=1536,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=settings.pinecone_environment),
            )
        self._index = self._pc.Index(settings.pinecone_index_name)

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        by_ns: dict[str, list] = {}
        for chunk, vec in zip(chunks, vectors):
            ns = chunk.metadata.get("department", "general")
            by_ns.setdefault(ns, []).append(
                {"id": chunk.chunk_id, "values": vec.tolist(), "metadata": {**chunk.metadata, "text": chunk.text}}
            )
        for ns, items in by_ns.items():
            self._index.upsert(vectors=items, namespace=ns)

    def query(
        self,
        query_vector: np.ndarray,
        top_k: int,
        namespace: str | None = None,
        allowed_access_levels: set[str] | None = None,
        document_type: str | None = None,
    ) -> list[tuple[Chunk, float]]:
        flt = {}
        if allowed_access_levels:
            flt["access_level"] = {"$in": list(allowed_access_levels)}
        if document_type:
            flt["document_type"] = document_type

        resp = self._index.query(
            vector=query_vector.tolist(),
            top_k=top_k,
            namespace=namespace,
            filter=flt or None,
            include_metadata=True,
        )
        results = []
        for match in resp.matches:
            meta = match.metadata or {}
            chunk = Chunk(
                doc_id=meta.get("doc_id", match.id),
                chunk_id=match.id,
                text=meta.get("text", ""),
                metadata=meta,
            )
            results.append((chunk, match.score))
        return results


def get_vector_store():
    if settings.pinecone_api_key:
        return PineconeVectorStore()
    return LocalVectorStore()
