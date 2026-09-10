"""Vector store for RAG retrieval with Qdrant backend and hybrid search.

Supports dense (sentence-transformers) + sparse (BM25) hybrid search via Qdrant.
Falls back to in-memory cosine similarity when Qdrant is unavailable.
"""

import logging
import math
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Qdrant client (optional)
_QDRANT_AVAILABLE = False
try:  # pragma: no cover
    from qdrant_client import QdrantClient, models  # type: ignore[import]
    from qdrant_client.http.models import (  # type: ignore[import]
        Distance,
        SparseIndexParams,
        SparseVectorParams,
        VectorParams,
    )

    _QDRANT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QDRANT_AVAILABLE = False
    QdrantClient = Any  # type: ignore[assignment,misc]
    models = Any  # type: ignore[assignment,misc]

# numpy is a project dependency but guard anyway for robustness
_NUMPY_AVAILABLE = False
try:  # pragma: no cover
    import numpy as np  # type: ignore[import]

    _NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMPY_AVAILABLE = False


class Retriever:
    """Vector store with hybrid search (dense + sparse) via Qdrant.

    Falls back to in-memory cosine similarity when Qdrant is unavailable.
    Maintains backwards-compatible interface with original Retriever.
    """

    def __init__(
        self,
        collection_name: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        vector_size: int | None = None,
        hnsw_m: int | None = None,
        hnsw_ef_construct: int | None = None,
        enable_hybrid: bool | None = None,
        dense_vector_name: str | None = None,
        sparse_vector_name: str | None = None,
    ) -> None:
        """Initialize retriever.

        Parameters
        ----------
        collection_name : str | None
            Qdrant collection name. Uses settings default if None.
        url : str | None
            Qdrant server URL. Uses settings default if None.
        api_key : str | None
            Qdrant API key. Uses settings default if None.
        vector_size : int | None
            Dense vector dimension. Uses settings default if None.
        hnsw_m : int | None
            HNSW M parameter. Uses settings default if None.
        hnsw_ef_construct : int | None
            HNSW ef_construct parameter. Uses settings default if None.
        enable_hybrid : bool | None
            Enable hybrid search. Uses settings default if None.
        dense_vector_name : str | None
            Name for dense vector. Uses settings default if None.
        sparse_vector_name : str | None
            Name for sparse vector. Uses settings default if None.
        """
        # Import settings lazily to avoid circular imports
        from src.core.config import settings

        self._collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self._url = url or settings.QDRANT_URL
        self._api_key = api_key or settings.QDRANT_API_KEY
        self._vector_size = vector_size or settings.QDRANT_VECTOR_SIZE
        self._hnsw_m = hnsw_m or settings.QDRANT_HNSW_M
        self._hnsw_ef_construct = hnsw_ef_construct or settings.QDRANT_HNSW_EF_CONSTRUCT
        self._enable_hybrid = enable_hybrid if enable_hybrid is not None else settings.QDRANT_ENABLE_HYBRID
        self._dense_vector_name = dense_vector_name or settings.QDRANT_DENSE_VECTOR_NAME
        self._sparse_vector_name = sparse_vector_name or settings.QDRANT_SPARSE_VECTOR_NAME

        # Qdrant client (lazy initialization)
        self._client: Any = None
        self._use_qdrant = False
        self._collection_created = False

        # Fallback in-memory storage (used when Qdrant unavailable)
        self._vectors: list[list[float]] = []
        self._metadata: list[dict[str, Any]] = []
        self._dimension: int = 0

        # Try to initialize Qdrant client
        if _QDRANT_AVAILABLE:
            self._init_qdrant_client()

    def _init_qdrant_client(self) -> None:
        """Initialize Qdrant client and create collection if needed."""
        try:
            self._client = QdrantClient(url=self._url, api_key=self._api_key)
            # Test connection
            self._client.get_collections()
            self._use_qdrant = True
            logger.info("Qdrant client initialized: %s", self._url)
        except Exception as e:
            logger.warning("Qdrant unavailable, falling back to in-memory storage: %s", e)
            self._client = None
            self._use_qdrant = False

    def _ensure_collection(self) -> None:
        """Create Qdrant collection if it doesn't exist."""
        if not self._use_qdrant or self._collection_created:
            return

        try:
            collections = self._client.get_collections()
            exists = any(c.name == self._collection_name for c in collections.collections)

            if not exists:
                # Create collection with dense + sparse vectors
                vectors_config = {
                    self._dense_vector_name: VectorParams(
                        size=self._vector_size,
                        distance=Distance.COSINE,
                        hnsw_config=models.HnswConfigDiff(
                            m=self._hnsw_m,
                            ef_construct=self._hnsw_ef_construct,
                        ),
                    ),
                }

                if self._enable_hybrid:
                    vectors_config[self._sparse_vector_name] = SparseVectorParams(
                        index=SparseIndexParams(on_disk=False)
                    )

                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=vectors_config,
                )
                logger.info("Created Qdrant collection: %s", self._collection_name)
            else:
                logger.debug("Qdrant collection already exists: %s", self._collection_name)

            self._collection_created = True
        except Exception as e:
            logger.error("Failed to create Qdrant collection: %s", e)
            self._use_qdrant = False

    # ------------------------------------------------------------------
    # Public API (backwards compatible)
    # ------------------------------------------------------------------

    def add(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
        texts: list[str] | None = None,
    ) -> None:
        """Index vectors with optional metadata and texts (for sparse vectors).

        Parameters
        ----------
        vectors : list[list[float]]
            Dense embedding vectors. All must have the same length.
        metadata : list[dict] | None
            Arbitrary metadata dict per vector. If None, empty dicts are stored.
        texts : list[str] | None
            Original texts for BM25 sparse vector generation. Required for hybrid search.
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

        if texts is not None and len(texts) != len(vectors):
            raise ValueError(f"texts length ({len(texts)}) must match vectors length ({len(vectors)})")

        # Validate dimensionality consistency on subsequent adds
        if self._dimension == 0:
            self._dimension = dim
        elif dim != self._dimension:
            raise ValueError(f"Dimension mismatch: existing vectors are {self._dimension}-D, new vectors are {dim}-D")

        if self._use_qdrant:
            self._add_to_qdrant(vectors, metadata, texts)
        else:
            self._add_to_memory(vectors, metadata)

    def _add_to_qdrant(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
        texts: list[str] | None,
    ) -> None:
        """Add vectors to Qdrant."""
        self._ensure_collection()

        # Generate sparse vectors if hybrid enabled and texts provided
        sparse_vectors = None
        if self._enable_hybrid and texts is not None:
            try:
                from src.features.rag.embedder import SparseEmbedder

                sparse_embedder = SparseEmbedder()
                # Fit on all texts seen so far + new texts
                all_texts = [m.get("text", "") for m in self._metadata] + texts
                sparse_embedder.fit(all_texts)
                sparse_vectors = sparse_embedder.embed(texts)
            except Exception as e:
                logger.warning("Failed to generate sparse vectors: %s", e)
                sparse_vectors = None

        points = []
        for i, (vector, meta) in enumerate(zip(vectors, metadata, strict=True)):
            point_id = str(uuid.uuid4())
            # Store text in metadata for sparse vector rebuilds
            if texts is not None:
                meta = {**meta, "text": texts[i]}

            vectors_dict = {self._dense_vector_name: vector}
            if sparse_vectors is not None and i < len(sparse_vectors):
                vectors_dict[self._sparse_vector_name] = models.SparseVector(**sparse_vectors[i])

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vectors_dict,
                    payload=meta,
                )
            )

        try:
            self._client.upsert(collection_name=self._collection_name, points=points)
            logger.debug("Added %d vectors to Qdrant (total: %d)", len(vectors), len(self._vectors) + len(vectors))
        except Exception as e:
            logger.error("Failed to add vectors to Qdrant: %s", e)
            self._use_qdrant = False
            self._add_to_memory(vectors, metadata)

    def _add_to_memory(self, vectors: list[list[float]], metadata: list[dict[str, Any]]) -> None:
        """Add vectors to in-memory fallback."""
        self._vectors.extend(vectors)
        self._metadata.extend(metadata)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        query_text: str | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the top_k most similar entries.

        Parameters
        ----------
        query_vector : list[float]
            Dense query vector.
        top_k : int
            Number of results to return.
        query_text : str | None
            Query text for sparse vector generation (hybrid search).
        filter_metadata : dict | None
            Metadata filters (e.g., {"source": "doc1", "user_id": 123}).

        Returns
        -------
        list[dict]
            Each dict contains 'score' (combined similarity) and 'metadata'.
        """
        if top_k <= 0:
            return []

        if self._use_qdrant:
            return self._search_qdrant(query_vector, top_k, query_text, filter_metadata)
        else:
            return self._search_memory(query_vector, top_k)

    def _search_qdrant(
        self,
        query_vector: list[float],
        top_k: int,
        query_text: str | None,
        filter_metadata: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Search using Qdrant with hybrid dense + sparse."""
        self._ensure_collection()

        try:
            # Build query filter
            query_filter = None
            if filter_metadata:
                conditions = [
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                    for key, value in filter_metadata.items()
                ]
                query_filter = models.Filter(must=conditions)

            # Prepare sparse vector if hybrid enabled and query_text provided
            sparse_vector = None
            if self._enable_hybrid and query_text is not None:
                try:
                    from src.features.rag.embedder import SparseEmbedder

                    sparse_embedder = SparseEmbedder()
                    # Need corpus for BM25 - get from existing metadata
                    corpus_texts = [m.get("text", "") for m in self._metadata if m.get("text")]
                    if corpus_texts:
                        sparse_embedder.fit(corpus_texts)
                        sparse_results = sparse_embedder.embed([query_text])
                        if sparse_results:
                            sparse_vector = models.SparseVector(**sparse_results[0])
                except Exception as e:
                    logger.warning("Failed to generate sparse query vector: %s", e)

            # Perform search
            if sparse_vector is not None and self._enable_hybrid:
                # Hybrid search using prefetch + query
                results = self._client.query_points(
                    collection_name=self._collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                    prefetch=[
                        models.Prefetch(
                            query=sparse_vector,
                            using=self._sparse_vector_name,
                            limit=top_k * 2,
                        )
                    ],
                )
            else:
                # Dense-only search
                results = self._client.query_points(
                    collection_name=self._collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )

            return [{"score": hit.score, "metadata": hit.payload or {}} for hit in results.points]

        except Exception as e:
            logger.error("Qdrant search failed, falling back to memory: %s", e)
            self._use_qdrant = False
            return self._search_memory(query_vector, top_k)

    def _search_memory(
        self,
        query_vector: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """In-memory cosine similarity search (fallback)."""
        if not self._vectors:
            return []

        if len(query_vector) != self._dimension:
            raise ValueError(
                f"Dimension mismatch: query vector is {len(query_vector)}-D, store vectors are {self._dimension}-D"
            )

        scores = [self._cosine_similarity(query_vector, v) for v in self._vectors]

        indexed_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        return [{"score": score, "metadata": self._metadata[idx]} for idx, score in indexed_scores]

    def clear(self) -> None:
        """Remove all stored vectors and metadata."""
        if self._use_qdrant:
            try:
                self._client.delete_collection(collection_name=self._collection_name)
                self._collection_created = False
                logger.info("Cleared Qdrant collection: %s", self._collection_name)
            except Exception as e:
                logger.error("Failed to clear Qdrant collection: %s", e)
        self._vectors.clear()
        self._metadata.clear()
        self._dimension = 0

    def delete_by_filter(self, filter_metadata: dict[str, Any]) -> int:
        """Delete points matching filter. Returns count deleted."""
        if self._use_qdrant:
            try:
                conditions = [
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                    for key, value in filter_metadata.items()
                ]
                query_filter = models.Filter(must=conditions)
                result = self._client.delete(
                    collection_name=self._collection_name,
                    points_selector=models.FilterSelector(filter=query_filter),
                )
                logger.info("Deleted %d points from Qdrant", result.deleted_count)
                return result.deleted_count
            except Exception as e:
                logger.error("Failed to delete from Qdrant: %s", e)
        return 0

    # ------------------------------------------------------------------
    # Dunders
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        if self._use_qdrant:
            try:
                info = self._client.get_collection(self._collection_name)
                return info.points_count or 0
            except Exception:
                pass
        return len(self._vectors)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two equal-length vectors."""
        if _NUMPY_AVAILABLE:
            a_np = np.asarray(a, dtype=np.float64)
            b_np = np.asarray(b, dtype=np.float64)
            dot = float(np.dot(a_np, b_np))
            norm_a = float(np.linalg.norm(a_np))
            norm_b = float(np.linalg.norm(b_np))
        else:
            dot = sum(x * y for x, y in zip(a, b, strict=False))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))

        denom = norm_a * norm_b
        if denom == 0.0:
            return 0.0
        return dot / denom
