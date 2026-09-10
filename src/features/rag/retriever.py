"""In-memory vector store for RAG retrieval.

Stores embedding vectors with associated metadata and retrieves the
closest matches by cosine similarity.  No external dependencies beyond
numpy (which is already a project requirement).
"""

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# numpy is a project dependency but guard anyway for robustness
_NUMPY_AVAILABLE = False
try:  # pragma: no cover
    import numpy as np  # type: ignore[import]

    _NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMPY_AVAILABLE = False


class Retriever:
    """Lightweight in-memory vector store with cosine-similarity search.

    All vectors must share the same dimensionality.
    """

    def __init__(self) -> None:
        self._vectors: list[list[float]] = []
        self._metadata: list[dict[str, Any]] = []
        self._dimension: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        """Index *vectors* with optional per-vector metadata.

        Parameters
        ----------
        vectors : list[list[float]]
            Dense embedding vectors.  All must have the same length.
        metadata : list[dict] | None
            Arbitrary metadata dict per vector.  If ``None``, empty dicts are
            stored.  Length must match *vectors*.
        """
        if not vectors:
            return

        dim = len(vectors[0])
        if dim == 0:
            raise ValueError("Vectors must have at least one dimension")

        for v in vectors:
            if len(v) != dim:
                raise ValueError(f"All vectors must have the same dimensionality (expected {dim}, got {len(v)})")

        if metadata is not None and len(metadata) != len(vectors):
            raise ValueError(f"metadata length ({len(metadata)}) must match vectors length ({len(vectors)})")

        if metadata is None:
            metadata = [{} for _ in vectors]

        # Validate dimensionality consistency on subsequent adds
        if self._dimension == 0:
            self._dimension = dim
        elif dim != self._dimension:
            raise ValueError(f"Dimension mismatch: existing vectors are {self._dimension}-D, new vectors are {dim}-D")

        self._vectors.extend(vectors)
        self._metadata.extend(metadata)
        logger.debug("Added %d vectors (total: %d)", len(vectors), len(self._vectors))

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the *top_k* most similar entries to *query_vector*.

        Returns
        -------
        list[dict]
            Each dict contains ``score`` (cosine similarity) and the
            original ``metadata`` dict.
        """
        if not self._vectors:
            return []

        if len(query_vector) != self._dimension:
            raise ValueError(
                f"Dimension mismatch: query vector is {len(query_vector)}-D, store vectors are {self._dimension}-D"
            )

        if top_k <= 0:
            return []

        scores = [self._cosine_similarity(query_vector, v) for v in self._vectors]

        # Rank by descending score
        indexed_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for idx, score in indexed_scores:
            results.append({"score": score, "metadata": self._metadata[idx]})

        return results

    def clear(self) -> None:
        """Remove all stored vectors and metadata."""
        self._vectors.clear()
        self._metadata.clear()
        self._dimension = 0

    # ------------------------------------------------------------------
    # Dunders
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._vectors)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two equal-length vectors.

        Falls back to a pure-Python implementation when numpy is unavailable.
        """
        if _NUMPY_AVAILABLE:
            a_np = np.asarray(a, dtype=np.float64)  # type: ignore[union-attr]
            b_np = np.asarray(b, dtype=np.float64)  # type: ignore[union-attr]
            dot = float(np.dot(a_np, b_np))  # type: ignore[union-attr]
            norm_a = float(np.linalg.norm(a_np))  # type: ignore[union-attr]
            norm_b = float(np.linalg.norm(b_np))  # type: ignore[union-attr]
        else:
            dot = sum(x * y for x, y in zip(a, b, strict=False))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))

        denom = norm_a * norm_b
        if denom == 0.0:
            return 0.0
        return dot / denom
