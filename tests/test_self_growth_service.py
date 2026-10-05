"""Unit tests for SelfGrowthService continuous learning logic."""

import pytest

from src.application.self_growth_service import GrowthStatus, SelfGrowthService
from src.domain.interfaces import ILLMProvider
from src.domain.models import (
    AnswerKey,
    ExamQuestion,
    KnowledgeCandidate,
    KnowledgeVerificationResult,
    RetrievalChunk,
)
from src.infrastructure.qdrant_store import QdrantVectorStore


class FakeLLMProvider(ILLMProvider):
    """Fake LLM Provider for deterministic testing of self-growth loop."""

    def __init__(
        self,
        candidate_to_return: KnowledgeCandidate | None = None,
        candidates_to_return: list[KnowledgeCandidate] | None = None,
        judge_result_to_return: KnowledgeVerificationResult | None = None,
        judge_results_map: dict[str, KnowledgeVerificationResult] | None = None,
        fixed_vector: list[float] | None = None,
    ):
        self.candidate_to_return = candidate_to_return
        self.candidates_to_return = candidates_to_return
        self.judge_result_to_return = judge_result_to_return
        self.judge_results_map = judge_results_map or {}
        self.fixed_vector = fixed_vector or [0.5, 0.5, 0.5, 0.5]

    def embed(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
        title: str | None = None,
        dimensionality: int = 4,
    ) -> list[float]:
        # Generate slightly varied vector based on title to avoid accidental collision in multi-tests
        if title and "Saga" in title:
            return [0.0, 0.9, 0.1, 0.0]
        return self.fixed_vector

    def embed_batch(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        dimensionality: int = 4,
    ) -> list[list[float]]:
        return [self.fixed_vector for _ in texts]

    def generate_explanation(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        return "Fake explanation"

    def chat_response(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        return "Fake chat response"

    def extract_knowledge_candidate(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> KnowledgeCandidate | None:
        return self.candidate_to_return

    def extract_knowledge_candidates(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> list[KnowledgeCandidate]:
        if self.candidates_to_return is not None:
            return self.candidates_to_return
        if self.candidate_to_return:
            return [self.candidate_to_return]
        return []

    def judge_knowledge(
        self,
        candidate: KnowledgeCandidate,
        question: ExamQuestion,
    ) -> KnowledgeVerificationResult:
        if candidate.title in self.judge_results_map:
            return self.judge_results_map[candidate.title]
        if self.judge_result_to_return:
            return self.judge_result_to_return
        return KnowledgeVerificationResult(
            is_approved=True,
            confidence_score=0.90,
            critique="Passes all checks",
            refined_title="Refined Title",
            refined_core_concept="Refined Core Concept",
            refined_trap_analysis="Refined Trap Analysis",
            tags=["Test"],
        )


@pytest.fixture
def mock_store() -> QdrantVectorStore:
    return QdrantVectorStore(
        collection_name="test-self-growth",
        location=":memory:",
        embedding_dimension=4,
    )


def test_self_growth_pipeline_create_new(
    mock_store: QdrantVectorStore, sample_question: ExamQuestion
):
    """Scenario: Valid insight candidate is approved by Judge and indexed as new insight."""
    candidate = KnowledgeCandidate(
        source_question_id=sample_question.id,
        title="サーキットブレーカーの役割",
        core_concept="カスケード障害の防止",
        trap_analysis="レートリミッターとの混同",
        practical_takeaway="指数バックオフの併用",
        dialogue_context="ユーザーとのディスカッション",
        proposed_tags=["Microservices"],
    )
    judge_result = KnowledgeVerificationResult(
        is_approved=True,
        confidence_score=0.92,
        critique="事実と整合している",
        refined_title="サーキットブレーカーの核心",
        refined_core_concept="カスケード障害の防止",
        refined_trap_analysis="レートリミッターとの混同",
        tags=["Microservices", "Reliability"],
    )

    fake_llm = FakeLLMProvider(
        candidate_to_return=candidate,
        judge_result_to_return=judge_result,
        fixed_vector=[0.1, 0.2, 0.3, 0.4],
    )
    service = SelfGrowthService(
        vector_store=mock_store,
        llm_provider=fake_llm,
        confidence_threshold=0.85,
        dedup_threshold=0.88,
    )

    report = service.process_dialogue_to_knowledge(
        question=sample_question,
        dialogue_history=[{"role": "user", "content": "なぜウは違うのですか？"}],
    )

    assert report.status == GrowthStatus.CREATED_NEW
    assert report.saved_insight is not None
    assert report.saved_insight.title == "サーキットブレーカーの核心"
    assert report.saved_insight.confidence_score == 0.92

    # Verify stored in Qdrant
    insights = mock_store.list_insights()
    assert len(insights) == 1
    assert insights[0].title == "サーキットブレーカーの核心"


def test_self_growth_pipeline_rejected_by_judge(
    mock_store: QdrantVectorStore, sample_question: ExamQuestion
):
    """Scenario: Hallucination or low confidence candidate is rejected by Judge gatekeeper."""
    candidate = KnowledgeCandidate(
        source_question_id=sample_question.id,
        title="誤った主張",
        core_concept="誤った概念",
        trap_analysis="誤ったトラップ",
        practical_takeaway="危険な指針",
        dialogue_context="誤認に基づく発言",
        proposed_tags=["Wrong"],
    )
    judge_result = KnowledgeVerificationResult(
        is_approved=False,
        confidence_score=0.40,
        critique="公式正解と明確に矛盾しておりハルシネーションである",
        refined_title="不採用",
        refined_core_concept="",
        refined_trap_analysis="",
        tags=[],
    )

    fake_llm = FakeLLMProvider(
        candidate_to_return=candidate,
        judge_result_to_return=judge_result,
    )
    service = SelfGrowthService(
        vector_store=mock_store,
        llm_provider=fake_llm,
        confidence_threshold=0.85,
    )

    report = service.process_dialogue_to_knowledge(
        question=sample_question,
        dialogue_history=[{"role": "user", "content": "間違った思い込み"}],
    )

    assert report.status == GrowthStatus.REJECTED_JUDGE_FAILED
    assert report.saved_insight is None
    assert "審査官" in report.message

    # Verify NOT stored in Qdrant
    assert len(mock_store.list_insights()) == 0


def test_self_growth_pipeline_deduplication_and_merge(
    mock_store: QdrantVectorStore, sample_question: ExamQuestion
):
    """Scenario: Semantically duplicate insight is merged into existing record without bloating."""
    candidate = KnowledgeCandidate(
        source_question_id=sample_question.id,
        title="既存知見と重複する洞察",
        core_concept="カスケード障害の抑止",
        trap_analysis="レートリミットとの違い",
        practical_takeaway="追加の運用指針",
        dialogue_context="追試対話",
        proposed_tags=["Microservices"],
    )
    judge_result = KnowledgeVerificationResult(
        is_approved=True,
        confidence_score=0.95,
        critique="追加知見として妥当",
        refined_title="サーキットブレーカーの核心（統合後）",
        refined_core_concept="カスケード障害の抑止と自動復帰",
        refined_trap_analysis="レートリミットとの違い",
        tags=["Microservices", "Resilience"],
    )

    # Use identical vector for first and second calls to trigger similarity > 0.88
    same_vector = [0.5, 0.5, 0.5, 0.5]
    fake_llm = FakeLLMProvider(
        candidate_to_return=candidate,
        judge_result_to_return=judge_result,
        fixed_vector=same_vector,
    )
    service = SelfGrowthService(
        vector_store=mock_store,
        llm_provider=fake_llm,
        confidence_threshold=0.85,
        dedup_threshold=0.88,
    )

    # 1st insertion: Creates new
    report1 = service.process_dialogue_to_knowledge(
        sample_question, [{"role": "user", "content": "1回目"}]
    )
    assert report1.status == GrowthStatus.CREATED_NEW
    assert len(mock_store.list_insights()) == 1

    # 2nd insertion with identical vector: Merges into existing
    report2 = service.process_dialogue_to_knowledge(
        sample_question, [{"role": "user", "content": "2回目"}]
    )
    assert report2.status == GrowthStatus.UPDATED_EXISTING
    assert report2.similarity_score > 0.99
    # Must STILL have only 1 record (no duplicate bloat)
    assert len(mock_store.list_insights()) == 1
    updated_insight = mock_store.list_insights()[0]
    assert "[追加補足]" in updated_insight.core_concept


def test_self_growth_pipeline_multi_candidates(
    mock_store: QdrantVectorStore, sample_question: ExamQuestion
):
    """Scenario: Multiple distinct insights are extracted from dialogue and independently indexed."""
    candidate1 = KnowledgeCandidate(
        source_question_id=sample_question.id,
        title="サーキットブレーカーの閾値設計",
        core_concept="連続失敗閾値とハーフオープン状態の推移",
        trap_analysis="レートリミットとの違い",
        practical_takeaway="指数バックオフとサーキットブレーカーの併用",
        dialogue_context="対話1",
        proposed_tags=["Microservices"],
    )
    candidate2 = KnowledgeCandidate(
        source_question_id=sample_question.id,
        title="Sagaパターンの補償トランザクション",
        core_concept="オーケストレーション型での結果整合性担保",
        trap_analysis="2PCとの違い",
        practical_takeaway="ローカルACIDと補償処理の設計",
        dialogue_context="対話2",
        proposed_tags=["DistributedTx"],
    )

    judge_map = {
        "サーキットブレーカーの閾値設計": KnowledgeVerificationResult(
            is_approved=True,
            confidence_score=0.92,
            critique="妥当な技術的知見",
            refined_title="サーキットブレーカーの状態推移と閾値設計",
            refined_core_concept="連続失敗閾値とハーフオープン状態",
            refined_trap_analysis="レートリミットとの違い",
            tags=["Microservices"],
        ),
        "Sagaパターンの補償トランザクション": KnowledgeVerificationResult(
            is_approved=True,
            confidence_score=0.94,
            critique="Sagaパターンの解説として正確",
            refined_title="Sagaパターンにおける補償トランザクション設計",
            refined_core_concept="結果整合性と補償処理",
            refined_trap_analysis="2PCとの違い",
            tags=["DistributedTx"],
        ),
    }

    fake_llm = FakeLLMProvider(
        candidates_to_return=[candidate1, candidate2],
        judge_results_map=judge_map,
    )
    service = SelfGrowthService(
        vector_store=mock_store,
        llm_provider=fake_llm,
        confidence_threshold=0.85,
    )

    report = service.process_dialogue_to_knowledge(
        question=sample_question,
        dialogue_history=[{"role": "user", "content": "CBとSagaの両方について質問"}],
    )

    assert len(report.reports) == 2
    assert report.created_count == 2
    assert report.updated_count == 0
    assert report.rejected_count == 0

    # Both insights must be indexed in Qdrant
    insights = mock_store.list_insights()
    assert len(insights) == 2
    titles = [ins.title for ins in insights]
    assert "サーキットブレーカーの状態推移と閾値設計" in titles
    assert "Sagaパターンにおける補償トランザクション設計" in titles


def test_self_growth_pipeline_multi_candidates_mixed_approval(
    mock_store: QdrantVectorStore, sample_question: ExamQuestion
):
    """Scenario: Multiple candidates with mixed approval (1 approved, 1 rejected)."""
    valid_cand = KnowledgeCandidate(
        source_question_id=sample_question.id,
        title="有益な知見",
        core_concept="正しい概念",
        trap_analysis="正しいトラップ",
        practical_takeaway="正しい指針",
        dialogue_context="対話A",
        proposed_tags=["Valid"],
    )
    invalid_cand = KnowledgeCandidate(
        source_question_id=sample_question.id,
        title="雑談・誤認",
        core_concept="誤った概念",
        trap_analysis="誤ったトラップ",
        practical_takeaway="危険な指針",
        dialogue_context="対話B",
        proposed_tags=["Invalid"],
    )

    judge_map = {
        "有益な知見": KnowledgeVerificationResult(
            is_approved=True,
            confidence_score=0.91,
            critique="正確",
            refined_title="有益な知見（精査済）",
            refined_core_concept="正しい概念",
            refined_trap_analysis="正しいトラップ",
            tags=["Valid"],
        ),
        "雑談・誤認": KnowledgeVerificationResult(
            is_approved=False,
            confidence_score=0.35,
            critique="不正確で有用性なし",
            refined_title="却下",
            refined_core_concept="",
            refined_trap_analysis="",
            tags=[],
        ),
    }

    fake_llm = FakeLLMProvider(
        candidates_to_return=[valid_cand, invalid_cand],
        judge_results_map=judge_map,
    )
    service = SelfGrowthService(
        vector_store=mock_store,
        llm_provider=fake_llm,
        confidence_threshold=0.85,
    )

    report = service.process_dialogue_to_knowledge(
        question=sample_question,
        dialogue_history=[{"role": "user", "content": "混在した対話"}],
    )

    assert len(report.reports) == 2
    assert report.created_count == 1
    assert report.rejected_count == 1

    # Only approved insight must be indexed in Qdrant
    insights = mock_store.list_insights()
    assert len(insights) == 1
    assert insights[0].title == "有益な知見（精査済）"
