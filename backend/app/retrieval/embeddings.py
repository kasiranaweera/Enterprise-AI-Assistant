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
from backend.app.logging_config import get_logger

settings = get_settings()
logger = get_logger("retrieval.embeddings")


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


class PineconeInferenceEmbedder:
    """Uses Pinecone's serverless inference API (multilingual-e5-large)
    when PINECONE_API_KEY is available and no OpenAI key is provided.
    Runs fast, free of extra API keys, producing 1024-d neural embeddings."""

    def __init__(self):
        from pinecone import Pinecone

        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self.model = "multilingual-e5-large"

    def embed(self, texts: list[str]) -> np.ndarray:
        res = self._pc.inference.embed(
            model=self.model,
            inputs=texts,
            parameters={"input_type": "passage", "truncate": "END"},
        )
        return np.array([item.values for item in res], dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        res = self._pc.inference.embed(
            model=self.model,
            inputs=[text],
            parameters={"input_type": "query", "truncate": "END"},
        )
        return np.array(res[0].values, dtype=np.float32)


class ResilientEmbedder:
    """Wraps a remote embedder (OpenAI / Pinecone inference) and falls
    back to the local TF-IDF embedder on ANY runtime failure — not just
    construction failure. Construction can succeed (the SDK client just
    stores an API key) while the first real network call still fails,
    which is exactly the "Vector DB / embedding provider failure"
    scenario the spec calls out.

    Important: once we fall back during `embed()` (index-build time),
    we stay on the local embedder for the rest of this instance's life
    so query vectors land in the same space as the indexed document
    vectors — mixing spaces would make similarity scores meaningless.
    """

    def __init__(self, primary):
        self._primary = primary
        self._fallback = LocalTfidfEmbedder()
        self._degraded = False

    @property
    def degraded(self) -> bool:
        return self._degraded

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self._degraded:
            try:
                return self._primary.embed(texts)
            except Exception as exc:  # noqa: BLE001 - graceful degradation
                logger.warning("embedder_failed_falling_back", extra={"error": str(exc)})
                self._degraded = True
        return self._fallback.embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        if not self._degraded:
            try:
                return self._primary.embed_query(text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("embedder_query_failed_falling_back", extra={"error": str(exc)})
                self._degraded = True
                # The fallback hasn't been fit yet if we degrade on the very
                # first query — nothing we can do but surface the error,
                # since there's no corpus text available at this call site
                # to fit against.
                if not self._fallback._fitted:
                    raise
        return self._fallback.embed_query(text)


def get_embedder():
    if settings.openai_api_key:
        return ResilientEmbedder(OpenAIEmbedder())
    if settings.pinecone_api_key:
        try:
            return ResilientEmbedder(PineconeInferenceEmbedder())
        except Exception as exc:  # noqa: BLE001
            logger.warning("pinecone_embedder_init_failed", extra={"error": str(exc)})
    return LocalTfidfEmbedder()
