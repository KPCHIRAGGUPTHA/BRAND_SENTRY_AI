"""
Unit Tests for Document Chunking Service
"""
import pytest
from backend.app.services.extraction import ExtractedDocument, ExtractedPage
from backend.app.services.chunking import DocumentChunker, GuidelineChunk


def test_chunking_short_text():
    """Verify that text shorter than chunk_size_words produces a single chunk."""
    chunker = DocumentChunker(chunk_size_words=50, chunk_overlap_words=10)
    page = ExtractedPage(page_number=1, text="Brand colors are blue and gold.", char_count=31)
    doc = ExtractedDocument(
        filename="test.txt",
        file_type="txt",
        page_count=1,
        total_characters=31,
        pages=[page],
    )

    chunks = chunker.chunk_document("doc-123", doc)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc-123_c0"
    assert chunks[0].document_id == "doc-123"
    assert chunks[0].page_number == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "Brand colors are blue and gold."
    assert chunks[0].word_count == 6


def test_chunking_long_text_with_overlap():
    """Verify that text longer than chunk_size_words is split with expected overlap."""
    chunker = DocumentChunker(chunk_size_words=20, chunk_overlap_words=5)
    # Generate 45 words: word_0 to word_44
    words = [f"word_{i}" for i in range(45)]
    text = " ".join(words)

    page = ExtractedPage(page_number=1, text=text, char_count=len(text))
    doc = ExtractedDocument(
        filename="policy.txt",
        file_type="txt",
        page_count=1,
        total_characters=len(text),
        pages=[page],
    )

    chunks = chunker.chunk_document("doc-long", doc)
    # Step = 20 - 5 = 15.
    # Chunk 0: words 0..19 (20 words)
    # Chunk 1: words 15..34 (20 words)
    # Chunk 2: words 30..44 (15 words)
    assert len(chunks) == 3

    # Check IDs & metadata
    assert chunks[0].chunk_id == "doc-long_c0"
    assert chunks[1].chunk_id == "doc-long_c1"
    assert chunks[2].chunk_id == "doc-long_c2"

    # Check overlap: words 15..19 must be in both chunk 0 and chunk 1
    assert "word_15" in chunks[0].text
    assert "word_19" in chunks[0].text
    assert "word_15" in chunks[1].text
    assert "word_19" in chunks[1].text

    # No empty chunks
    for c in chunks:
        assert len(c.text.strip()) > 0
        assert c.word_count > 0


def test_chunking_multi_page_preserves_page_numbers():
    """Verify that multi-page documents maintain correct page_number metadata."""
    chunker = DocumentChunker(chunk_size_words=50, chunk_overlap_words=10)
    page1 = ExtractedPage(page_number=1, text="Page one rules on trademarks.", char_count=30)
    page2 = ExtractedPage(page_number=2, text="Page two rules on disclaimers.", char_count=30)

    doc = ExtractedDocument(
        filename="multi.pdf",
        file_type="pdf",
        page_count=2,
        total_characters=60,
        pages=[page1, page2],
    )

    chunks = chunker.chunk_document("doc-multi", doc)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[0].chunk_index == 0
    assert chunks[1].page_number == 2
    assert chunks[1].chunk_index == 1


def test_chunking_invalid_overlap_raises():
    """Verify that overlap >= chunk_size raises ValueError."""
    with pytest.raises(ValueError):
        DocumentChunker(chunk_size_words=20, chunk_overlap_words=20)
