"""RAG (Retrieval-Augmented Generation) module for KRYVARACODE.

Provides text chunking, embedding, vector retrieval, and prompt augmentation.
All heavy dependencies (sentence-transformers, torch) are optional — the module
gracefully falls back to lighter alternatives or becomes unavailable.
"""

from typing import Any

from src.features.rag.augmenter import Augmenter
from src.features.rag.chunker import Chunker
from src.features.rag.retriever import Retriever

RAG_AVAILABLE: bool = True

try:  # pragma: no cover
    from src.features.rag.embedder import Embedder
except ImportError:  # pragma: no cover
    RAG_AVAILABLE = False
    Embedder: Any = None  # type: ignore[assignment,misc]

__all__ = ["Chunker", "Embedder", "Retriever", "Augmenter", "RAG_AVAILABLE"]
