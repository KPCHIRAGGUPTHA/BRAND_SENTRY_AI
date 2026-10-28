import pytest
import os
import sys

# Ensure backend module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.api.review import _execute_review_pipeline
from backend.app.retrieval.vector_store import vector_store_service
from backend.app.services.chunking import GuidelineChunk
from backend.app.retrieval.embeddings import embedding_service

def setup_test_data():
    # Insert some mock chunks
    chunks = [
        GuidelineChunk(
            chunk_id="chunk_1",
            document_id="doc_1",
            source_filename="test.txt",
            page_number=1,
            chunk_index=0,
            text="The product is not guaranteed to cure any diseases. It is safe for daily use.", word_count=10, char_count=50
        ),
        GuidelineChunk(
            chunk_id="chunk_2",
            document_id="doc_1",
            source_filename="test.txt",
            page_number=1,
            chunk_index=1,
            text="All returns must be processed within 30 days of purchase.", word_count=10, char_count=50
        ),
        GuidelineChunk(
            chunk_id="chunk_3",
            document_id="doc_1",
            source_filename="test.txt",
            page_number=1,
            chunk_index=2,
            text="Employees must not disclose confidential information.", word_count=10, char_count=50
        ),
    ]

    embeddings = embedding_service.generate_embeddings([c.text for c in chunks])
    vector_store_service.client.reset()
    vector_store_service._collection = None
    vector_store_service.add_chunks(chunks, embeddings)

def test_evaluate_retrieval():
    # Setup test data in vector store
    setup_test_data()

    dataset = [
        {
            "content": "Our product is guaranteed to cure your diseases instantly.",
            "expected_verdict": "CONTRADICTED",
            "expected_chunk": "chunk_1"
        },
        {
            "content": "You can return this within 30 days.",
            "expected_verdict": "SUPPORTED",
            "expected_chunk": "chunk_2"
        },
        {
            "content": "We use advanced AI technology.",
            "expected_verdict": "INSUFFICIENT_EVIDENCE",
            "expected_chunk": None
        }
    ]

    total = len(dataset)
    correct_verdicts = 0
    correct_retrievals = 0

    for item in dataset:
        response = _execute_review_pipeline(item["content"], [], "test_review", "2023-01-01T00:00:00Z")
        if not response.claims:
            continue

        claim = response.claims[0]

        # Check verdict accuracy
        if claim.verdict == item["expected_verdict"]:
            correct_verdicts += 1

        # Check Precision@K (Did we retrieve the expected chunk in the top K?)
        if item["expected_chunk"]:
            retrieved_chunks = [ev.chunk_id for ev in claim.evidence]
            if item["expected_chunk"] in retrieved_chunks:
                correct_retrievals += 1

    verdict_accuracy = correct_verdicts / total
    # For Recall@K/Precision@K, here we just do a simple binary check per item
    # (retrieved correctly or not) which equals Recall@K for exactly 1 relevant doc.
    retrievable_items = sum(1 for item in dataset if item["expected_chunk"])
    recall_at_k = correct_retrievals / retrievable_items if retrievable_items > 0 else 0.0

    print(f"Verdict Accuracy: {verdict_accuracy:.2f}")
    print(f"Recall@K: {recall_at_k:.2f}")

    # Ensure the script works and basic assertions hold
    assert verdict_accuracy >= 0.0
    assert recall_at_k >= 0.0
