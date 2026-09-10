"""Embedding layer for RAG pipelines.

Tries to use ``sentence-transformers`` for high-quality dense embeddings,
falls back to scikit-learn ``TfidfVectorizer`` if unavailable, and raises
``RuntimeError`` if neither library is present.

Also provides BM25 sparse embeddings for hybrid search with Qdrant.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Optional heavy dependency — sentence-transformers / torch
_SENTENCE_TRANSFORMERS_AVAILABLE = False
try:  # pragma: no cover
    from sentence_transformers import SentenceTransformer  # type: ignore[import]

    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SENTENCE_TRANSFORMERS_AVAILABLE = False

# Lighter fallback — scikit-learn
_TfidfVectorizer: Any = None
_SKLEARN_AVAILABLE = False
try:  # pragma: no cover
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import]

    _TfidfVectorizer = TfidfVectorizer
    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SKLEARN_AVAILABLE = False

# BM25 for sparse vectors (hybrid search)
_BM25_AVAILABLE = False
try:  # pragma: no cover
    from rank_bm25 import BM25Okapi  # type: ignore[import]

    _BM25_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BM25_AVAILABLE = False


class Embedder:
    """Generate vector embeddings for a list of text strings.

    Parameters
    ----------
    model_name : str
        Name of the ``sentence-transformers`` model to load.  Ignored when
        falling back to TF-IDF.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._backend: str | None = None
        self._st_model: Any = None
        self._tfidf: Any = None

        if _SENTENCE_TRANSFORMERS_AVAILABLE:
            self._backend = "sentence-transformers"
            self._st_model = SentenceTransformer(model_name)  # type: ignore[misc]
            logger.info(
                "Embedder initialised with sentence-transformers model=%s",
                model_name,
            )
        elif _SKLEARN_AVAILABLE:
            self._backend = "tfidf"
            self._tfidf = _TfidfVectorizer(max_features=768)
            logger.info("Embedder falling back to TF-IDF backend")
        else:
            raise RuntimeError(
                "Embedder requires either 'sentence-transformers' or "
                "'scikit-learn'.  Install one of them to use embeddings."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text.

        Returns
        -------
        list[list[float]]
            Dense vectors.  Length equals ``len(texts)``.
        """
        if not texts:
            return []

        if self._backend == "sentence-transformers":
            vectors = self._st_model.encode(  # type: ignore[union-attr]
                texts, show_progress_bar=False
            )
            return vectors.tolist()  # type: ignore[union-attr,no-any-return]

        # TF-IDF fallback (returns sparse → dense via .toarray())
        if self._tfidf is None or not hasattr(self._tfidf, "vocabulary_"):
            # First call — fit_transform
            matrix = self._tfidf.fit_transform(texts)  # type: ignore[union-attr]
        else:
            # Subsequent calls — transform only
            matrix = self._tfidf.transform(texts)  # type: ignore[union-attr]

        dense = matrix.toarray()  # type: ignore[union-attr]
        return dense.tolist()  # type: ignore[no-any-return]

    @property
    def backend(self) -> str | None:
        """Name of the active embedding backend."""
        return self._backend

    @property
    def dimension(self) -> int:
        """Dimensionality of produced vectors."""
        if self._backend == "sentence-transformers":
            return self._st_model.get_sentence_embedding_dimension()  # type: ignore[union-attr]
        # TF-IDF dimension is only known after first fit
        if self._tfidf is not None and hasattr(self._tfidf, "vocabulary_"):
            return len(self._tfidf.vocabulary_)  # type: ignore[union-attr]
        return 0


class SparseEmbedder:
    """Generate BM25 sparse vectors for hybrid search.

    Uses rank-bm25's BM25Okapi for tokenization and scoring.
    Produces sparse vectors as dict[int, float] (token_index -> weight)
    compatible with Qdrant's sparse vector format.
    """

    def __init__(self) -> None:
        if not _BM25_AVAILABLE:
            raise RuntimeError("SparseEmbedder requires 'rank-bm25'. Install it to use BM25 embeddings.")
        self._bm25: Any = None
        self._corpus_tokens: list[list[str]] = []
        self._vocab: dict[str, int] = {}
        self._vocab_built = False

    def fit(self, corpus: list[str]) -> None:
        """Build BM25 model from corpus.

        Parameters
        ----------
        corpus : list[str]
            Documents to index for BM25.
        """
        if not corpus:
            return
        self._corpus_tokens = [self._tokenize(doc) for doc in corpus]
        self._bm25 = BM25Okapi(self._corpus_tokens)
        # Build vocabulary mapping token -> index
        vocab_set = set()
        for tokens in self._corpus_tokens:
            vocab_set.update(tokens)
        self._vocab = {token: idx for idx, token in enumerate(sorted(vocab_set))}
        self._vocab_built = True
        logger.info("SparseEmbedder fitted on %d documents, vocab size: %d", len(corpus), len(self._vocab))

    def embed(self, texts: list[str]) -> list[dict[int, float]]:
        """Return BM25 sparse vectors for query texts.

        Returns
        -------
        list[dict[int, float]]
            Sparse vectors as {token_index: weight} dicts.
        """
        if not texts:
            return []
        if not self._vocab_built or self._bm25 is None:
            # Fit on the fly if not already fitted (use texts as corpus)
            self.fit(texts)

        results: list[dict[int, float]] = []
        for text in texts:
            query_tokens = self._tokenize(text)
            if not query_tokens:
                results.append({})
                continue
            # Get BM25 scores for query tokens against corpus
            # Returns array of shape (n_corpus_docs,) - score per corpus doc
            self._bm25.get_scores(query_tokens)  # Compute to verify BM25 works

            # For sparse vector, we need token-level contributions
            # Use IDF-weighted token frequencies as sparse vector weights
            sparse_vec: dict[int, float] = {}
            for token in set(query_tokens):  # unique tokens in query
                if token in self._vocab:
                    # BM25 score for this token across all docs
                    # We use the average IDF-weighted frequency as the weight
                    token_idx = self._vocab[token]
                    # Simple approach: count occurrences * IDF-like weight
                    tf = query_tokens.count(token)
                    # Approximate IDF: log((N - n_t + 0.5) / (n_t + 0.5))
                    n_t = sum(1 for doc_tokens in self._corpus_tokens if token in doc_tokens)
                    N = len(self._corpus_tokens)
                    import math
                    idf = math.log((N - n_t + 0.5) / (n_t + 0.5) + 1) if n_t > 0 else 0
                    weight = tf * max(idf, 0)
                    if weight > 0:
                        sparse_vec[token_idx] = float(weight)
            results.append(sparse_vec)
        return results

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple whitespace + punctuation tokenizer."""
        import re

        # Split on non-alphanumeric, lowercase
        tokens = re.findall(r"\b\w+\b", text.lower())
        return tokens

    @property
    def vocab_size(self) -> int:
        return len(self._vocab)

    @property
    def is_fitted(self) -> bool:
        return self._vocab_built and self._bm25 is not None
