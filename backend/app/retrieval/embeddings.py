"""
Embeddings abstraction.

If OPENAI_API_KEY is set we use OpenAI's text-embedding-3-small
(cheap, good quality). If not, we fall back to a local TF-IDF ->
truncated-SVD embedding (scikit-learn) so the whole POC runs with
*zero* external API keys — useful for the evaluator to run offline.
Both paths expose the same `.embed(texts) -> np.ndarray` interface so
callers never know which backend is active.
"""
import numpy as np

from backend.app.config import get_settings

settings = get_settings()


class OpenAIEmbedder:
    def __init__(self):
        from langchain_openai import OpenAIEmbeddings

        self._client = OpenAIEmbeddings(
            model="text-embedding-3-small", api_key=settings.openai_api_key
        )

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = self._client.embed_documents(texts)
        return np.array(vectors, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return np.array(self._client.embed_query(text), dtype=np.float32)


class LocalTfidfEmbedder:
    """Zero-dependency-on-external-API fallback. Fits a TF-IDF + SVD
    model over the corpus at index time; queries are projected into
    the same space. Good enough for a POC / offline demo, not meant
    to rival real embeddings."""

    def __init__(self, n_components: int = 128):
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(max_features=20000, stop_words="english")
        self._svd = TruncatedSVD(n_components=n_components, random_state=42)
        self._fitted = False

    def fit(self, corpus: list[str]) -> None:
        tfidf = self._vectorizer.fit_transform(corpus)
        n_comp = min(self._svd.n_components, tfidf.shape[1] - 1, tfidf.shape[0] - 1)
        n_comp = max(n_comp, 1)
        self._svd.n_components = n_comp
        self._svd.fit(tfidf)
        self._fitted = True

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            self.fit(texts)
        tfidf = self._vectorizer.transform(texts)
        vecs = self._svd.transform(tfidf)
        return vecs.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Embedder must be fit on the corpus before embedding a query.")
        tfidf = self._vectorizer.transform([text])
        return self._svd.transform(tfidf)[0].astype(np.float32)


def get_embedder():
    if settings.openai_api_key:
        return OpenAIEmbedder()
    return LocalTfidfEmbedder()
