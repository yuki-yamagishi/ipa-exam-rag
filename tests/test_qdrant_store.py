"""Unit tests for QdrantVectorStore using in-memory mode."""

import pytest

from src.domain.models import DocType, ExamQuestion, LearnedInsight
from src.infrastructure.qdrant_store import QdrantVectorStore


@pytest.fixture
def in_memory_qdrant() -> QdrantVectorStore:
    """Create isolated in-memory Qdrant store for tests."""
    return QdrantVectorStore(
        collection_name="test-ipa-exam-rag",
        location=":memory:",
        embedding_dimension=4,  # Use small dimension for fast unit tests
    )


def test_qdrant_upsert_and_hybrid_search(
    in_memory_qdrant: QdrantVectorStore, sample_question: ExamQuestion
):
    """Test question insertion and retrieval in Qdrant."""
    embedding = [0.5, 0.5, 0.5, 0.5]
    in_memory_qdrant.upsert_exam_questions([sample_question], [embedding])

    # Search with identical vector
    results = in_memory_qdrant.search_hybrid(
        query_text="サーキットブレーカー",
        query_dense_vector=[0.5, 0.5, 0.5, 0.5],
        limit=5,
        filter_doc_types=[DocType.EXAM_QUESTION],
    )
    assert len(results) == 1
    assert results[0].doc_type == DocType.EXAM_QUESTION
    assert "マイクロサービス" in results[0].content
    assert results[0].score > 0.99


def test_qdrant_learned_insight_upsert_and_dedup(in_memory_qdrant: QdrantVectorStore):
    """Test learned insight indexing and duplicate detection."""
    insight = LearnedInsight(
        id="insight_123",
        source_question_id="2025-SA-AM2-Q01",
        title="サーキットブレーカーの閾値設定",
        core_concept="スレッド枯渇防止",
        trap_analysis="レートリミットとの違い",
        practical_takeaway="リトライ回数の制限",
        confidence_score=0.95,
        tags=["マイクロサービス"],
    )
    vec = [0.0, 1.0, 0.0, 0.0]
    in_memory_qdrant.upsert_insight(insight, vec)

    # Verify listing
    insights = in_memory_qdrant.list_insights()
    assert len(insights) == 1
    assert insights[0].id == "insight_123"

    # Test deduplication match (exact or close vector)
    matched, score = in_memory_qdrant.find_most_similar_insight(
        query_dense_vector=[0.0, 1.0, 0.0, 0.0],
        threshold=0.88,
    )
    assert matched is not None
    assert matched.id == "insight_123"
    assert score > 0.99

    # Test distinct vector below threshold
    not_matched, score_low = in_memory_qdrant.find_most_similar_insight(
        query_dense_vector=[1.0, 0.0, 0.0, 0.0],
        threshold=0.88,
    )
    assert not_matched is None
    assert score_low < 0.88
