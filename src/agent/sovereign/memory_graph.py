"""
Sovereign Memory Graph for KRYVARACODE Omega-Prime.
A recursive memory system that stores lessons learned, failure patterns,
and successful strategic pivots to ensure long-term continuity.
"""

import logging
import uuid
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union, Protocol

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Interface for generating and comparing semantic embeddings."""

    def encode(self, text: str) -> List[float]: ...
    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float: ...


class CosineSimilarityProvider:
    """Standard cosine similarity implementation for memory embeddings."""

    def encode(self, text: str) -> List[float]:
        # In production, this would call an actual embedding model (e.g., Sentence-BERT)
        # For the core architecture, we provide a structural placeholder.
        return []

    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)


@dataclass
class MemoryNode:
    """A unit of knowledge in the Sovereign Memory Graph."""

    id: str
    tier: str  # "episodic" or "semantic"
    category: str  # e.g., "failure_pattern", "strategic_pivot", "tool_constraint"
    content: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Set[str] = field(default_factory=set)
    related_nodes: List[str] = field(default_factory=list)
    confidence: float = 1.0
    embedding: Optional[List[float]] = None


class SovereignMemory:
    """
    The Recursive Memory system.
    Implements tiered storage: Episodic (raw events) and Semantic (distilled knowledge).
    """

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self._nodes: Dict[str, MemoryNode] = {}
        self._index_by_tag: Dict[str, List[str]] = {}
        self.embedding_provider = embedding_provider or CosineSimilarityProvider()

    def commit(
        self,
        tier: str,
        category: str,
        content: str,
        context: Dict[str, Any],
        tags: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        Store a memory node in the specified tier (episodic or semantic).
        """
        node_id = f"mem_{uuid.uuid4().hex[:8]}"

        # If no embedding provided, try to generate one
        final_embedding = embedding
        if final_embedding is None:
            final_embedding = self.embedding_provider.encode(content)

        node = MemoryNode(
            id=node_id,
            tier=tier,
            category=category,
            content=content,
            context=context,
            tags=set(tags) if tags is not None else set(),
            embedding=final_embedding,
        )

        self._nodes[node_id] = node

        for tag in node.tags:
            if tag not in self._index_by_tag:
                self._index_by_tag[tag] = []
            self._index_by_tag[tag].append(node_id)

        logger.info(f"Committed {tier} memory ({category}): {node_id}")
        return node_id

    def query(
        self,
        query_text: str,
        tier: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[MemoryNode]:
        """
        Retrieve relevant memories using a combination of tag filtering
        and semantic similarity.
        """
        candidates = []

        if tags:
            for tag in tags:
                if tag in self._index_by_tag:
                    candidates.extend(
                        [self._nodes[nid] for nid in self._index_by_tag[tag]]
                    )
        else:
            candidates = list(self._nodes.values())

        if tier:
            candidates = [n for n in candidates if n.tier == tier]

        # Generate embedding for the query
        query_vec = self.embedding_provider.encode(query_text)
        scored_results = []
        query_words = set(query_text.lower().split())

        for node in candidates:
            # 1. Semantic Score
            semantic_score = 0.0
            if query_vec and node.embedding:
                semantic_score = self.embedding_provider.similarity(
                    query_vec, node.embedding
                )

            # 2. Keyword Fallback (only if semantic is low or unavailable)
            if semantic_score == 0:
                content_words = set(node.content.lower().split())
                overlap = len(query_words.intersection(content_words))
                # Normalize keyword overlap to 0.0 - 1.0 range
                semantic_score = min(1.0, overlap / (len(query_words) + 1e-6))

            scored_results.append((semantic_score, node))

        scored_results.sort(key=lambda x: x[0], reverse=True)

        unique_nodes = []
        seen_ids = set()
        for score, node in scored_results:
            if node.id not in seen_ids:
                unique_nodes.append(node)
                seen_ids.add(node.id)
            if len(unique_nodes) >= limit:
                break

        return unique_nodes

    def query_patterns(
        self, context: Union[str, Dict[str, Any]], tags: Optional[List[str]] = None
    ) -> List[MemoryNode]:
        """
        Specialized query to find failure patterns based on context.
        """
        if isinstance(context, str):
            query_text = context
        else:
            query_text = " ".join([f"{k}:{v}" for k, v in context.items()])
        return self.query(query_text=query_text, tags=tags)

    def commit_lesson(
        self,
        category: str,
        content: str,
        context: Dict[str, Any],
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Convenience method to commit a semantic lesson.
        """
        return self.commit(
            tier="semantic",
            category=category,
            content=content,
            context=context,
            tags=tags,
        )

    def link_nodes(self, node_a: str, node_b: str):
        """Create a causal link between two memories."""
        if node_a in self._nodes and node_b in self._nodes:
            self._nodes[node_a].related_nodes.append(node_b)
            self._nodes[node_b].related_nodes.append(node_a)

    def distill_lessons(
        self, episodic_node_ids: List[str], synthesizer_agent: Any
    ) -> List[str]:
        """
        The Lesson Extraction Loop.
        Analyzes raw episodic traces and uses an LLM (via synthesizer_agent)
        to distill them into high-level semantic rules.
        """
        if not episodic_node_ids:
            return []

        traces = []
        for nid in episodic_node_ids:
            if nid in self._nodes:
                node = self._nodes[nid]
                traces.append(
                    f"ID: {node.id} | Content: {node.content} | Context: {node.context}"
                )

        trace_block = "\n".join(traces)
        prompt = (
            "Analyze the following episodic execution traces from an autonomous agent. "
            "Distill them into a set of concise, generalizable semantic rules (lessons learned). "
            "Each rule should follow the format: 'RULE: [Rule Name] | CONTENT: [The rule text] | TAGS: [tag1, tag2]'.\n\n"
            f"Traces:\n{trace_block}"
        )

        try:
            response = synthesizer_agent.synthesize_lesson(prompt)

            distilled_ids = []
            for line in response.split("\n"):
                if line.startswith("RULE:"):
                    parts = line.split("|")
                    if len(parts) >= 3:
                        name = parts[0].replace("RULE:", "").strip()
                        content = parts[1].replace("CONTENT:", "").strip()
                        tags = [
                            t.strip() for t in parts[2].replace("TAGS:", "").split(",")
                        ]

                        mid = self.commit(
                            tier="semantic",
                            category="distilled_rule",
                            content=f"{name}: {content}",
                            context={"source_traces": episodic_node_ids},
                            tags=tags,
                        )
                        distilled_ids.append(mid)

            return distilled_ids
        except Exception as e:
            logger.error(f"Lesson extraction failed: {e}")
            return []


# Global singleton
sovereign_memory = SovereignMemory()
