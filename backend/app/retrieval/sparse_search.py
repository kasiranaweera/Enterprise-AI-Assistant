"""
Sparse (keyword) retrieval using BM25 — the "Sparse Search" leg of
hybrid retrieval required by the spec. BM25 is excellent at exact
term/acronym/error-code matches (e.g. "ERR-504", "PCI-DSS") that
dense embeddings often blur together.
"""
import re

from rank_bm25 import BM25Okapi

from backend.app.retrieval.document_loader import Chunk


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9\-]+", text.lower())


class SparseIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        tokenized_corpus = [_tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

    def search(self, query: str, top_k: int = 10) -> list[tuple[Chunk, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
