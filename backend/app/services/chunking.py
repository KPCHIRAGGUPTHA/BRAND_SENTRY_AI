"""
Deterministic Text Chunking Service for BrandSentry AI.
Chunks document pages with configurable window size, overlap, and rich metadata.
"""
from dataclasses import dataclass
from typing import List, Optional
from backend.app.core.config import settings
from backend.app.services.extraction import ExtractedDocument


@dataclass
class GuidelineChunk:
    chunk_id: str
    document_id: str
    source_filename: str
    page_number: Optional[int]
    chunk_index: int
    text: str
    word_count: int
    char_count: int


class DocumentChunker:
    """
    Splits extracted document pages into overlapping chunks preserving citations and source metadata.
    Uses deterministic whitespace-based word splitting approximating ~400 tokens / 50 tokens overlap.
    """

    def __init__(
        self,
        chunk_size_words: Optional[int] = None,
        chunk_overlap_words: Optional[int] = None,
    ):
        self.chunk_size_words = chunk_size_words or settings.CHUNK_SIZE_WORDS
        self.chunk_overlap_words = chunk_overlap_words or settings.CHUNK_OVERLAP_WORDS

        if self.chunk_overlap_words >= self.chunk_size_words:
            raise ValueError("chunk_overlap_words must be smaller than chunk_size_words")

    def chunk_document(self, document_id: str, extracted_doc: ExtractedDocument) -> List[GuidelineChunk]:
        """
        Splits an ExtractedDocument into GuidelineChunk instances page by page.
        """
        chunks: List[GuidelineChunk] = []
        global_chunk_idx = 0

        for page in extracted_doc.pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            words = page_text.split()
            if not words:
                continue

            # If page text is within chunk size limit, keep it as a single chunk
            if len(words) <= self.chunk_size_words:
                chunk_id = f"{document_id}_c{global_chunk_idx}"
                chunks.append(
                    GuidelineChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        source_filename=extracted_doc.filename,
                        page_number=page.page_number,
                        chunk_index=global_chunk_idx,
                        text=page_text,
                        word_count=len(words),
                        char_count=len(page_text),
                    )
                )
                global_chunk_idx += 1
            else:
                # Sliding window chunking
                step = self.chunk_size_words - self.chunk_overlap_words
                for start_idx in range(0, len(words), step):
                    end_idx = min(start_idx + self.chunk_size_words, len(words))
                    chunk_words = words[start_idx:end_idx]
                    chunk_text = " ".join(chunk_words).strip()

                    if chunk_text:
                        chunk_id = f"{document_id}_c{global_chunk_idx}"
                        chunks.append(
                            GuidelineChunk(
                                chunk_id=chunk_id,
                                document_id=document_id,
                                source_filename=extracted_doc.filename,
                                page_number=page.page_number,
                                chunk_index=global_chunk_idx,
                                text=chunk_text,
                                word_count=len(chunk_words),
                                char_count=len(chunk_text),
                            )
                        )
                        global_chunk_idx += 1

                    # Break if we reached the end of words for this page
                    if end_idx >= len(words):
                        break

        return chunks


document_chunker = DocumentChunker()
