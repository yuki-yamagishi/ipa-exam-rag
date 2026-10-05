"""Integration tests for RAG Retrieval & AI Explanation API (ISSUE-015 / DoD-B4)."""

from collections.abc import Generator
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
    """In-memory hermetic mock for Qdrant vector store."""

    def __init__(self, initial_chunks: list[RetrievalChunk] | None = None) -> None:
        self.chunks = initial_chunks or []
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
        pass

    def search_hybrid(
        self,
        query_text: str,
        query_dense_vector: list[float],
        limit: int = 5,
        filter_doc_types: list[DocType] | None = None,
    ) -> list[RetrievalChunk]:
        return self.chunks[:limit]

    def find_most_similar_insight(
        self, query_dense_vector: list[float], threshold: float = 0.88
    ) -> tuple[LearnedInsight | None, float]:
        return None, 0.0

    def list_insights(self, limit: int = 50) -> list[LearnedInsight]:
        return []

    def count(self) -> int:
        return len(self.stored_questions) + len(self.chunks)


class MockLLMProvider(ILLMProvider):
    """Mock LLM provider supporting deterministic responses and fault simulation."""

    def __init__(self, fail_generate: bool = False, fail_embed: bool = False) -> None:
        self.fail_generate = fail_generate
        self.fail_embed = fail_embed

    def embed(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
        title: str | None = None,
        dimensionality: int = 768,
    ) -> list[float]:
        if self.fail_embed:
            raise RuntimeError("Simulated embedding API error")
        return [0.1] * dimensionality

    def embed_batch(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        dimensionality: int = 768,
    ) -> list[list[float]]:
        if self.fail_embed:
            raise RuntimeError("Simulated batch embedding API error")
        return [[0.1] * dimensionality for _ in texts]

    def generate_explanation(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        if self.fail_generate:
            raise RuntimeError("Simulated Gemini API 503 Service Unavailable")
        return (
            f"【AI根拠解説】設問「{question.id}」の正解は「{question.correct_answer}」です。"
            f"あなたの選択「{user_choice}」について、参照チャンク数: {len(context_chunks)}件をもとに解説します。"
        )

    def chat_response(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        return "Chat response"

    def extract_knowledge_candidate(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> KnowledgeCandidate | None:
        return None

    def extract_knowledge_candidates(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> list[KnowledgeCandidate]:
        return []

    def verify_knowledge_candidate(
        self,
        candidate: KnowledgeCandidate,
        question: ExamQuestion,
    ) -> KnowledgeVerificationResult:
        raise NotImplementedError


def sample_questions() -> list[ExamQuestion]:
    return [
        ExamQuestion(
            id="2025-SA-AM2-Q01",
            year=2025,
            term="秋期",
            exam_type="SA",
            question_number=1,
            category="テクノロジ系",
            question_text="コンパイラの構文解析処理に関する記述として適切なものはどれか。",
            choices=[
                ExamChoice(key=AnswerKey.A, text="字句解析の直前に実行される"),
                ExamChoice(key=AnswerKey.I, text="構文木（構文解析木）を生成する"),
                ExamChoice(key=AnswerKey.U, text="中間コード最適化を行う"),
                ExamChoice(key=AnswerKey.E, text="機械語への直接変換を行う"),
            ],
            correct_answer=AnswerKey.I,
            explanation="構文解析は字句解析で得られたトークン列を解析し、抽象構文木を生成します。",
            keywords=["コンパイラ", "構文解析", "構文木"],
        ),
    ]


@pytest.fixture
def rag_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """TestClient configured with mock vector store, mock LLM, and hermetic DB."""
    test_db_path = tmp_path / "test_rag.db"
    test_repo = SQLitePracticeHistoryRepository(db_path=test_db_path)

    sample_chunks = [
        RetrievalChunk(
            id="chunk-01",
            content="構文解析器は文脈自由文法に基づいて構文解析木を構築する。",
            score=0.88,
            doc_type=DocType.EXAM_QUESTION,
            metadata={"question_id": "2025-SA-AM2-Q01"},
        )
    ]
    mock_vector = MockVectorStore(initial_chunks=sample_chunks)
    mock_llm = MockLLMProvider()
    mock_qrepo = MockQuestionRepository(sample_questions())

    app = create_app()
    app.dependency_overrides[get_history_repository] = lambda: test_repo
    app.dependency_overrides[get_vector_store] = lambda: mock_vector
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    app.dependency_overrides[get_question_repository] = lambda: mock_qrepo

    try:
        with TestClient(app) as client:
            client.mock_vector = mock_vector  # type: ignore[attr-defined]
            client.mock_llm = mock_llm  # type: ignore[attr-defined]
            client.mock_qrepo = mock_qrepo  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()


# --- Scenario 1: Grounded Technical Explanation Generation (Normal) ---
def test_scenario_1_explain_question_success(rag_client: TestClient):
    """シナリオ 1: 根拠付き技術解説生成 (正常系)"""
    payload = {
        "question_id": "2025-SA-AM2-Q01",
        "user_choice": "イ",
    }
    res = rag_client.post("/api/rag/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["question_id"] == "2025-SA-AM2-Q01"
    assert "構文解析木" in data["explanation"] or "AI根拠解説" in data["explanation"]
    assert len(data["context_chunks"]) == 1
    assert data["context_chunks"][0]["id"] == "chunk-01"
    assert data["context_chunks"][0]["score"] == 0.88


# --- Scenario 2: Question Not Found 404 Guard (Abnormal) ---
def test_scenario_2_explain_question_not_found(rag_client: TestClient):
    """シナリオ 2: 存在しない設問 ID 指定時の 404 ガード (異常系)"""
    payload = {
        "question_id": "INVALID-QID-999",
        "user_choice": "ア",
    }
    res = rag_client.post("/api/rag/explain", json=payload)
    assert res.status_code == 404
    assert "Question not found: INVALID-QID-999" in res.json()["detail"]


# --- Scenario 3: Invalid Choice Key Validation (Abnormal / 422) ---
def test_scenario_3_invalid_choice_key(rag_client: TestClient):
    """シナリオ 3: 不正な選択肢キーのバリデーション (異常系 / 422)"""
    payload = {
        "question_id": "2025-SA-AM2-Q01",
        "user_choice": "X",
    }
    res = rag_client.post("/api/rag/explain", json=payload)
    assert res.status_code == 422


# --- Scenario 4: Fallback Explanation on LLM Error (Fault-tolerance) ---
def test_scenario_4_fallback_explanation_on_llm_error(tmp_path: Path):
    """シナリオ 4: LLM 呼び出し失敗時のフォールバック解説返却 (耐障害系)"""
    test_db_path = tmp_path / "test_rag_err.db"
    test_repo = SQLitePracticeHistoryRepository(db_path=test_db_path)
    mock_vector = MockVectorStore()
    failing_llm = MockLLMProvider(fail_generate=True)
    mock_qrepo = MockQuestionRepository(sample_questions())

    app = create_app()
    app.dependency_overrides[get_history_repository] = lambda: test_repo
    app.dependency_overrides[get_vector_store] = lambda: mock_vector
    app.dependency_overrides[get_llm_provider] = lambda: failing_llm
    app.dependency_overrides[get_question_repository] = lambda: mock_qrepo

    try:
        with TestClient(app) as client:
            payload = {
                "question_id": "2025-SA-AM2-Q01",
                "user_choice": "ア",
            }
            res = client.post("/api/rag/explain", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert "【公式正解】: (イ)" in data["explanation"]
            assert "構文解析は字句解析で得られたトークン列を解析し" in data["explanation"]
            assert "LLM API の接続が利用できないため" in data["explanation"]
    finally:
        app.dependency_overrides.clear()


# --- Scenario 5: Automatic Vector Store Seeding on Startup (Normal / Initial Startup) ---
def test_scenario_5_auto_seed_on_startup(tmp_path: Path):
    """シナリオ 5: 起動時 Qdrant 自動シード投入 (正常系 / 初期起動)"""
    test_db_path = tmp_path / "test_rag_seed.db"
    test_repo = SQLitePracticeHistoryRepository(db_path=test_db_path)

    # Empty mock vector store (count = 0)
    empty_vector = MockVectorStore(initial_chunks=[])
    assert empty_vector.count() == 0

    mock_llm = MockLLMProvider()
    mock_qrepo = MockQuestionRepository(sample_questions())

    app = create_app()
    app.dependency_overrides[get_history_repository] = lambda: test_repo
    app.dependency_overrides[get_vector_store] = lambda: empty_vector
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    app.dependency_overrides[get_question_repository] = lambda: mock_qrepo

    try:
        # Starting TestClient triggers the lifespan context manager
        with TestClient(app):
            # Lifespan should have detected count == 0 and executed auto-seed
            assert empty_vector.count() == len(sample_questions())
            assert len(empty_vector.stored_questions) == len(sample_questions())
            assert empty_vector.stored_questions[0].id == "2025-SA-AM2-Q01"
    finally:
        app.dependency_overrides.clear()
