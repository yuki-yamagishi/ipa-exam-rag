"""Integration tests for RAG Self-Growth & Background Save API (ISSUE-017 / DoD-B6)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.domain.interfaces import ILLMProvider, IVectorStore
from src.domain.models import (
    AnswerKey,
    DocType,
    ExamChoice,
    ExamQuestion,
    KnowledgeCandidate,
    KnowledgeVerificationResult,
    LearnedInsight,
    RetrievalChunk,
)
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.presentation.api.deps import (
    get_history_repository,
    get_llm_provider,
    get_question_repository,
    get_vector_store,
)
from src.presentation.api.main import create_app


class MockQuestionRepository:
    """Hermetic mock repository for exam questions."""

    def __init__(self, questions: list[ExamQuestion] | None = None) -> None:
        self.questions = questions or []
        self._map = {q.id: q for q in self.questions}

    def get_all_questions(self) -> list[ExamQuestion]:
        return list(self.questions)

    def get_question_by_id(self, question_id: str) -> ExamQuestion | None:
        return self._map.get(question_id)


class MockVectorStore(IVectorStore):
    """In-memory hermetic mock for Qdrant vector store supporting insights."""

    def __init__(self, initial_insights: list[LearnedInsight] | None = None) -> None:
        self.insights: list[LearnedInsight] = initial_insights or []
        self.stored_questions: list[ExamQuestion] = []
        self.stored_embeddings: list[list[float]] = []

    def setup_collection(self, collection_name: str | None = None) -> None:
        pass

    def upsert_exam_questions(
        self, questions: list[ExamQuestion], embeddings: list[list[float]]
    ) -> None:
        self.stored_questions.extend(questions)
        self.stored_embeddings.extend(embeddings)

    def upsert_insight(self, insight: LearnedInsight, embedding: list[float]) -> None:
        # Update if existing ID, else append
        for i, existing in enumerate(self.insights):
            if existing.id == insight.id:
                self.insights[i] = insight
                return
        self.insights.append(insight)

    def search_hybrid(
        self,
        query_text: str,
        query_dense_vector: list[float],
        limit: int = 5,
        filter_doc_types: list[DocType] | None = None,
    ) -> list[RetrievalChunk]:
        return []

    def find_most_similar_insight(
        self, query_dense_vector: list[float], threshold: float = 0.88
    ) -> tuple[LearnedInsight | None, float]:
        return None, 0.0

    def list_insights(self, limit: int = 50) -> list[LearnedInsight]:
        return self.insights[:limit]

    def count(self) -> int:
        return len(self.stored_questions) + len(self.insights)


class MockLLMProvider(ILLMProvider):
    """Mock LLM provider supporting knowledge extraction and judging."""

    def __init__(self, candidates_count: int = 2) -> None:
        self.candidates_count = candidates_count

    def embed(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
        title: str | None = None,
        dimensionality: int = 768,
    ) -> list[float]:
        return [0.1] * dimensionality

    def embed_batch(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        dimensionality: int = 768,
    ) -> list[list[float]]:
        return [[0.1] * dimensionality for _ in texts]

    def generate_explanation(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        return ""

    def chat_response(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        return ""

    def chat_stream(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> Iterator[str]:
        yield ""

    def extract_knowledge_candidate(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> KnowledgeCandidate | None:
        return KnowledgeCandidate(
            source_question_id=question.id,
            title="単一知見候補",
            core_concept="構文解析の概念",
            trap_analysis="字句解析との混同",
            practical_takeaway="フェーズの違いを理解する",
            dialogue_context="ユーザーの質問対話コンテキスト",
            proposed_tags=["コンパイラ"],
        )

    def extract_knowledge_candidates(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> list[KnowledgeCandidate]:
        return [
            KnowledgeCandidate(
                source_question_id=question.id,
                title=f"知見候補 {i}",
                core_concept=f"構文解析の概念 {i}",
                trap_analysis=f"字句解析との混同 {i}",
                practical_takeaway=f"フェーズの違いを理解する {i}",
                dialogue_context=f"ユーザーの質問対話コンテキスト {i}",
                proposed_tags=["コンパイラ"],
            )
            for i in range(1, self.candidates_count + 1)
        ]

    def judge_knowledge(
        self,
        candidate: KnowledgeCandidate,
        question: ExamQuestion,
    ) -> KnowledgeVerificationResult:
        return KnowledgeVerificationResult(
            is_approved=True,
            confidence_score=0.95,
            critique="正確で価値の高い知見です。",
            refined_title=candidate.title,
            refined_core_concept=candidate.core_concept,
            refined_trap_analysis=candidate.trap_analysis,
            tags=candidate.proposed_tags,
        )


def sample_question() -> ExamQuestion:
    return ExamQuestion(
        id="2025-SA-AM2-Q01",
        year=2025,
        season="秋期",
        exam_type="SA",
        question_number=1,
        category="システムアーキテクチャ",
        question_text="コンパイラの構文解析に関する記述として、適切なものはどれか。",
        choices=[
            ExamChoice(key="ア", text="トークン列を入力として構文木を生成する。"),
            ExamChoice(key="イ", text="ソースコードから識別子を切り出す。"),
            ExamChoice(key="ウ", text="ターゲット命令に直接変換する。"),
            ExamChoice(key="エ", text="中間コードの最適化を行う。"),
        ],
        correct_answer="ア",
        explanation="構文解析はトークン列から構文木を構築するフェーズです。",
        keywords=["コンパイラ", "構文解析"],
    )


def sample_insight() -> LearnedInsight:
    return LearnedInsight(
        id="insight_001",
        source_question_id="2025-SA-AM2-Q01",
        title="構文解析と字句解析の混同トラップ",
        core_concept="構文解析は構文木の構築を行う",
        trap_analysis="トークン分割は字句解析の責務",
        practical_takeaway="コンパイラフロントエンドの順序を意識する",
        confidence_score=0.92,
        is_verified=True,
        tags=["コンパイラ", "構文解析"],
    )


@pytest.fixture
def client_factory(tmp_path: Path):
    """Factory fixture creating test client with hermetic overrides."""

    def _create(
        initial_questions: list[ExamQuestion] | None = None,
        initial_insights: list[LearnedInsight] | None = None,
        candidates_count: int = 2,
    ) -> tuple[TestClient, MockQuestionRepository, MockVectorStore, MockLLMProvider]:
        db_path = tmp_path / "test_self_growth.db"
        history_repo = SQLitePracticeHistoryRepository(db_path=db_path)
        question_repo = MockQuestionRepository(initial_questions or [sample_question()])
        vector_store = MockVectorStore(initial_insights or [])
        llm_provider = MockLLMProvider(candidates_count=candidates_count)

        app = create_app()
        app.dependency_overrides[get_history_repository] = lambda: history_repo
        app.dependency_overrides[get_question_repository] = lambda: question_repo
        app.dependency_overrides[get_vector_store] = lambda: vector_store
        app.dependency_overrides[get_llm_provider] = lambda: llm_provider

        client = TestClient(app)
        return client, question_repo, vector_store, llm_provider

    return _create


def test_scenario_1_save_knowledge_accepted(client_factory):
    """シナリオ 1: 正常系 - 知見保存バックグラウンド投入 (202 Accepted 即時返却)."""
    client, _, _, _ = client_factory()

    response = client.post(
        "/api/rag/save-knowledge",
        json={
            "question_id": "2025-SA-AM2-Q01",
            "dialogue_history": [
                {"role": "user", "content": "構文解析と字句解析の違いは？"},
                {
                    "role": "assistant",
                    "content": "字句解析がトークン化、構文解析が構文木生成です。",
                },
            ],
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["question_id"] == "2025-SA-AM2-Q01"
    assert "scheduled in background" in data["message"]


def test_scenario_2_parallel_judge_and_save_completion(client_factory):
    """シナリオ 2: 正常系 - 並列審査・バックグラウンド保存の完走."""
    client, _, vector_store, _ = client_factory(candidates_count=3)

    # TestClient in context manager executes background tasks upon request completion
    response = client.post(
        "/api/rag/save-knowledge",
        json={
            "question_id": "2025-SA-AM2-Q01",
            "dialogue_history": [
                {"role": "user", "content": "詳しく教えてください"},
                {"role": "assistant", "content": "解説です"},
            ],
        },
    )
    assert response.status_code == 202

    # Verify that background task completed and 3 insights were indexed in vector store
    assert len(vector_store.insights) == 3
    indexed_titles = {insight.title for insight in vector_store.insights}
    assert indexed_titles == {"知見候補 1", "知見候補 2", "知見候補 3"}


def test_scenario_3_save_knowledge_question_not_found(client_factory):
    """シナリオ 3: 異常系 - 存在しない設問 ID 指定時の 404 ガード."""
    client, _, _, _ = client_factory()

    response = client.post(
        "/api/rag/save-knowledge",
        json={
            "question_id": "INVALID-ID",
            "dialogue_history": [
                {"role": "user", "content": "質問です"},
            ],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Question not found: INVALID-ID"


def test_scenario_4_save_knowledge_invalid_request(client_factory):
    """シナリオ 4: 異常系 - 空の対話履歴等に対する 422 バリデーション."""
    client, _, _, _ = client_factory()

    # Empty dialogue_history
    response = client.post(
        "/api/rag/save-knowledge",
        json={
            "question_id": "2025-SA-AM2-Q01",
            "dialogue_history": [],
        },
    )
    assert response.status_code == 422

    # Missing dialogue_history
    response_missing = client.post(
        "/api/rag/save-knowledge",
        json={
            "question_id": "2025-SA-AM2-Q01",
        },
    )
    assert response_missing.status_code == 422


def test_scenario_5_list_insights_success(client_factory):
    """シナリオ 5: 正常系 - 蓄積知見一覧取得 (GET /api/rag/insights)."""
    initial = [sample_insight()]
    client, _, _, _ = client_factory(initial_insights=initial)

    response = client.get("/api/rag/insights?limit=10")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "insight_001"
    assert data[0]["title"] == "構文解析と字句解析の混同トラップ"
    assert data[0]["confidence_score"] == 0.92
