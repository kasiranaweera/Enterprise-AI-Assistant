"""
Standalone ingestion/sanity-check script.

Run with: python -m scripts.ingest_documents
Builds the hybrid index over backend/data/sample_docs and prints a
summary — useful to confirm the retrieval stack works before starting
the full FastAPI server, and as a quick offline demo of hybrid search.
"""
from backend.app.retrieval.hybrid_search import HybridRetriever


def main():
    retriever = HybridRetriever.instance()
    print(f"Loaded {len(retriever.chunks)} chunks from sample_docs.")

    demo_queries = [
        ("What caused the payment gateway outages?", "analyst"),
        ("data retention policy", "viewer"),
        ("kubernetes node pressure runbook", "administrator"),
    ]
    for query, role in demo_queries:
        print(f"\n=== Query: '{query}' (role={role}) ===")
        results = retriever.search(query=query, role=role, top_k=3)
        for r in results:
            print(f"  [{r.hybrid_score:.3f}] {r.chunk.doc_id} :: {r.chunk.text[:100]}...")


if __name__ == "__main__":
    main()
