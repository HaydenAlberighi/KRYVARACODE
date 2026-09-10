"""Prompt augmentation for RAG pipelines.

Injects retrieved context documents into a prompt string, with
configurable truncation to stay within token budget.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Separator between injected context documents
_SEPARATOR = "\n\n---\n\n"


class Augmenter:
    """Augment a prompt with retrieved context documents.

    Parameters
    ----------
    max_context_chars : int
        Maximum total character budget for injected context (default 2000).
        Documents are added in order until the budget is exhausted.
    """

    def __init__(self, max_context_chars: int = 2000) -> None:
        if max_context_chars <= 0:
            raise ValueError("max_context_chars must be positive")
        self.max_context_chars = max_context_chars

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def augment(
        self,
        prompt: str,
        context_docs: List[str | Dict[str, Any]],
    ) -> str:
        """Inject *context_docs* before *prompt*.

        Parameters
        ----------
        prompt : str
            The user's original prompt / query.
        context_docs : list[str | dict]
            Retrieved documents — either plain strings or dicts with at
            least a ``"text"`` or ``"content"`` key.

        Returns
        -------
        str
            The augmented prompt with context prepended, or the original
            prompt unchanged if *context_docs* is empty.
        """
        if not context_docs:
            return prompt

        context_parts: List[str] = []
        total_chars = 0

        for doc in context_docs:
            # Extract text from dict or use directly
            if isinstance(doc, dict):
                text = doc.get("text") or doc.get("content") or ""
                if not text:
                    continue
            else:
                text = str(doc)

            # Truncate individual document to remaining budget
            remaining = self.max_context_chars - total_chars
            if remaining <= 0:
                break

            if len(text) > remaining:
                text = text[:remaining]

            context_parts.append(text)
            total_chars += len(text)

        if not context_parts:
            return prompt

        context_block = _SEPARATOR.join(context_parts)
        augmented = (
            f"Use the following context to answer the question:\n\n"
            f"{context_block}\n\n"
            f"---\n\n"
            f"{prompt}"
        )

        logger.debug(
            "Augmented prompt with %d context doc(s), %d chars injected",
            len(context_parts),
            total_chars,
        )
        return augmented
