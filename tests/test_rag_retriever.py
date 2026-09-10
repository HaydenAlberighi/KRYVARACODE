"""Unit tests for src/features/rag/retriever.py and augmenter.py"""

import pytest

from src.features.rag.retriever import Retriever
from src.features.rag.augmenter import Augmenter


class TestRetriever:
    def test_empty_store(self):
        r = Retriever()
        results = r.search([1.0, 0.0], top_k=5)
        assert results == []

    def test_add_and_len(self):
        r = Retriever()
        r.add([[1.0, 0.0], [0.0, 1.0]])
        assert len(r) == 2

    def test_add_with_metadata(self):
        r = Retriever()
        r.add([[1.0, 0.0]], metadata=[{"source": "doc1"}])
        results = r.search([1.0, 0.0], top_k=1)
        assert results[0]["metadata"] == {"source": "doc1"}

    def test_search_exact_match(self):
        r = Retriever()
        r.add([[1.0, 0.0], [0.0, 1.0]])
        results = r.search([1.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0]["score"] == pytest.approx(1.0, abs=1e-6)
        assert results[0]["metadata"] == {}

    def test_search_returns_top_k(self):
        r = Retriever()
        r.add([[1.0, 0.0], [0.9, 0.1], [0.1, 0.9]])
        results = r.search([1.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0]["score"] >= results[1]["score"]

    def test_search_top_k_exceeds_size(self):
        r = Retriever()
        r.add([[1.0, 0.0]])
        results = r.search([1.0, 0.0], top_k=10)
        assert len(results) == 1

    def test_search_dimension_mismatch(self):
        r = Retriever()
        r.add([[1.0, 0.0, 0.0]])
        with pytest.raises(ValueError, match="Dimension mismatch"):
            r.search([1.0, 0.0], top_k=1)

    def test_add_dimension_mismatch(self):
        r = Retriever()
        r.add([[1.0, 0.0]])
        with pytest.raises(ValueError, match="Dimension mismatch"):
            r.add([[1.0, 0.0, 0.0]])

    def test_add_empty_vectors(self):
        r = Retriever()
        r.add([])
        assert len(r) == 0

    def test_add_metadata_length_mismatch(self):
        r = Retriever()
        with pytest.raises(ValueError, match="metadata length"):
            r.add([[1.0, 0.0]], metadata=[{"a": 1}, {"b": 2}])

    def test_clear(self):
        r = Retriever()
        r.add([[1.0, 0.0]])
        assert len(r) == 1
        r.clear()
        assert len(r) == 0
        assert r.search([1.0, 0.0]) == []

    def test_search_zero_top_k(self):
        r = Retriever()
        r.add([[1.0, 0.0]])
        assert r.search([1.0, 0.0], top_k=0) == []

    def test_orthogonal_vectors(self):
        r = Retriever()
        r.add([[1.0, 0.0], [0.0, 1.0]])
        results = r.search([1.0, 0.0], top_k=2)
        assert results[0]["score"] == pytest.approx(1.0, abs=1e-6)
        assert results[1]["score"] == pytest.approx(0.0, abs=1e-6)


class TestAugmenter:
    def test_empty_context(self):
        a = Augmenter()
        assert a.augment("Hello", []) == "Hello"

    def test_single_context(self):
        a = Augmenter()
        result = a.augment("What is X?", ["X is a thing."])
        assert "X is a thing." in result
        assert result.endswith("What is X?")

    def test_multiple_contexts(self):
        a = Augmenter()
        result = a.augment("Query", ["Doc A.", "Doc B."])
        assert "Doc A." in result
        assert "Doc B." in result
        assert "---" in result

    def test_truncation(self):
        a = Augmenter(max_context_chars=20)
        result = a.augment(
            "Q", ["This is a very long document that exceeds the budget"]
        )
        assert len(result) < 200

    def test_dict_context_with_text_key(self):
        a = Augmenter()
        result = a.augment("Q", [{"text": "Context value"}])
        assert "Context value" in result

    def test_dict_context_with_content_key(self):
        a = Augmenter()
        result = a.augment("Q", [{"content": "Content value"}])
        assert "Content value" in result

    def test_dict_context_empty_text_skipped(self):
        a = Augmenter()
        result = a.augment("Q", [{"text": ""}])
        assert result == "Q"

    def test_invalid_max_context_chars(self):
        with pytest.raises(ValueError, match="max_context_chars must be positive"):
            Augmenter(max_context_chars=0)
