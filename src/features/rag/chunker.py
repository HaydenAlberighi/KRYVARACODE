"""Text chunking for RAG pipelines.

Splits documents into fixed-size, overlapping chunks at sentence boundaries
to preserve semantic coherence for downstream retrieval.
"""

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class Chunker:
    """Splits text into overlapping chunks at sentence boundaries.

    Parameters
    ----------
    chunk_size : int
        Target maximum character count per chunk (default 512).
    overlap : int
        Number of characters to overlap between consecutive chunks (default 50).
    """

    # Sentence-ending punctuation followed by whitespace (used as primary split points)
    _SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, text: str) -> List[str]:
        """Split *text* into overlapping chunks.

        Returns
        -------
        list[str]
            Non-empty chunk strings, each at most ``self.chunk_size`` characters.
        """
        if not text or not text.strip():
            return []

        sentences = self._split_sentences(text)
        if not sentences:
            return []

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            # If a single sentence exceeds chunk_size, split it on word boundaries
            if len(sentence) > self.chunk_size:
                # Flush what we have so far
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                chunks.extend(self._split_long_sentence(sentence))
                continue

            # Check if adding this sentence would exceed the limit
            candidate = f"{current_chunk} {sentence}" if current_chunk else sentence
            if len(candidate) <= self.chunk_size:
                current_chunk = candidate
            else:
                # Flush current chunk and start a new one with overlap
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = self._apply_overlap(current_chunk, sentence)

        # Flush remaining
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        logger.debug("Chunked %d chars into %d chunks", len(text), len(chunks))
        return chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_sentences(self, text: str) -> List[str]:
        """Split text on sentence-ending punctuation."""
        parts = self._SENTENCE_RE.split(text)
        return [p for p in parts if p.strip()]

    def _apply_overlap(self, previous: str, next_sentence: str) -> str:
        """Carry the tail of *previous* into the next chunk as overlap."""
        if self.overlap <= 0 or not previous:
            return next_sentence
        tail = previous[-self.overlap :]
        # Prefer not to break mid-word
        space_idx = tail.find(" ")
        if space_idx != -1:
            tail = tail[space_idx + 1 :]
        return f"{tail} {next_sentence}"

    def _split_long_sentence(self, sentence: str) -> List[str]:
        """Break a sentence that exceeds chunk_size at word boundaries."""
        words = sentence.split()
        chunks: List[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}" if current else word
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                # If a single word is longer than chunk_size, force-include it
                if len(word) > self.chunk_size:
                    chunks.append(word)
                    current = ""
                else:
                    current = word

        if current.strip():
            chunks.append(current.strip())

        return chunks
