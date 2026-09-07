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
from backend.app.logging_config import get_logger
from backend.app.retrieval.document_loader import Chunk

settings = get_settings()
logger = get_logger("retrieval.vector_store")


class VectorStoreUnavailableError(Exception):
    """Raised when the configured vector store backend cannot serve a request."""

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
            self._dimension = 1536
        else:
            desc = self._pc.describe_index(settings.pinecone_index_name)
            self._dimension = getattr(desc, "dimension", 1536)
        self._index = self._pc.Index(settings.pinecone_index_name)

    def _fit_vector(self, vec: np.ndarray | list[float]) -> list[float]:
        v = np.asarray(vec, dtype=np.float32).ravel()
        if len(v) < self._dimension:
            v = np.pad(v, (0, self._dimension - len(v)))
        elif len(v) > self._dimension:
            v = v[: self._dimension]
        return v.tolist()

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        by_ns: dict[str, list] = {}
        for chunk, vec in zip(chunks, vectors):
            ns = chunk.metadata.get("department", "general")
            by_ns.setdefault(ns, []).append(
                {
                    "id": chunk.chunk_id,
                    "values": self._fit_vector(vec),
                    "metadata": {**chunk.metadata, "text": chunk.text},
                }
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
            vector=self._fit_vector(query_vector),
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


class ResilientVectorStore:
    """Wraps PineconeVectorStore and transparently falls back to an
    in-memory LocalVectorStore on ANY failure — connection errors, auth
    errors, timeouts, or the index/service being unavailable.

    This is what turns "Vector DB failures" (a required error-handling
    scenario in the spec) into graceful degradation instead of a 500:
    once a failure is seen, we log it once, flip to local, and keep the
    session usable for the rest of the request/process rather than
    retrying a dead backend on every call.
    """

    def __init__(self):
        self._local = LocalVectorStore()
        self._pinecone: PineconeVectorStore | None = None
        self._pinecone_failed = False
        try:
            self._pinecone = PineconeVectorStore()
        except Exception as exc:  # noqa: BLE001 - any backend failure degrades gracefully
            logger.warning("pinecone_init_failed", extra={"error": str(exc)})
            self._pinecone_failed = True

    @property
    def degraded(self) -> bool:
        return self._pinecone_failed

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        # Always mirror into local store so retrieval keeps working even
        # if Pinecone fails mid-session (e.g. after a successful init).
        self._local.upsert(chunks, vectors)
        if self._pinecone is not None and not self._pinecone_failed:
            try:
                self._pinecone.upsert(chunks, vectors)
            except Exception as exc:  # noqa: BLE001
                logger.warning("pinecone_upsert_failed", extra={"error": str(exc)})
                self._pinecone_failed = True

    def query(self, *args, **kwargs) -> list[tuple[Chunk, float]]:
        if self._pinecone is not None and not self._pinecone_failed:
            try:
                return self._pinecone.query(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("pinecone_query_failed_falling_back", extra={"error": str(exc)})
                self._pinecone_failed = True
        return self._local.query(*args, **kwargs)


def get_vector_store():
    if settings.pinecone_api_key:
        return ResilientVectorStore()
    return LocalVectorStore()
