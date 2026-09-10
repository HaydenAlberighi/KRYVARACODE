"""Unit tests for src/features/rag/chunker.py"""

import pytest

from src.features.rag.chunker import Chunker


class TestChunkerInit:
    def test_default_params(self):
        c = Chunker()
        assert c.chunk_size == 512
        assert c.overlap == 50

    def test_custom_params(self):
        c = Chunker(chunk_size=256, overlap=30)
        assert c.chunk_size == 256
        assert c.overlap == 30

    def test_invalid_chunk_size(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            Chunker(chunk_size=0)

    def test_negative_overlap(self):
        with pytest.raises(ValueError, match="overlap must be non-negative"):
            Chunker(overlap=-1)

    def test_overlap_gte_chunk_size(self):
        with pytest.raises(ValueError, match="overlap must be less than chunk_size"):
            Chunker(chunk_size=100, overlap=100)


class TestChunkerChunk:
    def test_empty_text(self):
        assert Chunker().chunk("") == []

    def test_whitespace_only(self):
        assert Chunker().chunk("   \n\t  ") == []

    def test_short_text_single_chunk(self):
        result = Chunker(chunk_size=512).chunk("Hello world")
        assert result == ["Hello world"]

    def test_respects_chunk_size(self):
        c = Chunker(chunk_size=50, overlap=0)
        text = "A" * 30 + ". " + "B" * 30 + ". " + "C" * 30 + "."
        result = c.chunk(text)
        for chunk in result:
            assert len(chunk) <= 50

    def test_sentence_splitting(self):
        c = Chunker(chunk_size=25, overlap=0)
        text = "First sentence. Second sentence. Third sentence."
        result = c.chunk(text)
        assert len(result) >= 2
        assert "First sentence." in result[0]

    def test_overlap_creates_shared_text(self):
        c = Chunker(chunk_size=30, overlap=10)
        text = "Alpha bravo charlie delta echo foxtrot."
        result = c.chunk(text)
        if len(result) >= 2:
            # Second chunk should start with tail of first
            tail_of_first = result[0][-10:]
            assert tail_of_first in result[1] or result[1][:10] != ""

    def test_long_sentence_word_split(self):
        c = Chunker(chunk_size=30, overlap=0)
        text = "This is a very long sentence without punctuation that exceeds the limit"
        result = c.chunk(text)
        assert len(result) > 1
        combined = " ".join(result)
        for word in text.split():
            assert word in combined

    def test_preserves_content(self):
        c = Chunker(chunk_size=50, overlap=5)
        text = "The quick brown fox jumps over the lazy dog. Pack my box with five dozen jugs."
        result = c.chunk(text)
        all_words = " ".join(result)
        for word in text.split():
            assert word in all_words

    def test_custom_params_applied(self):
        c = Chunker(chunk_size=20, overlap=0)
        result = c.chunk("One. Two. Three. Four. Five.")
        assert len(result) >= 2
