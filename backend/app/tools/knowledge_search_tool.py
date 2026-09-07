"""
Knowledge Search Tool — the RAG tool exposed to the agent graph.
Wraps HybridRetriever and returns structured, attributable results.
"""
from backend.app.guardrails.prompt_injection import screen_retrieved_content
from backend.app.retrieval.hybrid_search import HybridRetriever


async def knowledge_search(
    query: str, role: str, department_filter: str | None = None, document_type: str | None = None, top_k: int = 6
) -> list[dict]:
    retriever = HybridRetriever.instance()
    results = retriever.search(
        query=query, role=role, department_filter=department_filter, document_type=document_type, top_k=top_k
    )
    texts = [r.chunk.text for r in results]
    safe_texts = screen_retrieved_content(texts)

    return [
        {
            "doc_id": r.chunk.metadata["doc_id"],
            "chunk_id": r.chunk.chunk_id,
            "text": safe_text,
            "dense_score": round(float(r.dense_score), 4),
            "sparse_score": round(float(r.sparse_score), 4),
            "hybrid_score": round(float(r.hybrid_score), 4),
            "metadata": r.chunk.metadata,
        }
        for r, safe_text in zip(results, safe_texts)
    ]
