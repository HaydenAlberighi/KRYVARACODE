"""Embedding layer for RAG pipelines.

Tries to use ``sentence-transformers`` for high-quality dense embeddings,
falls back to scikit-learn ``TfidfVectorizer`` if unavailable, and raises
``RuntimeError`` if neither library is present.
"""

import logging
from typing import Any, List

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

    def embed(self, texts: List[str]) -> List[List[float]]:
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
