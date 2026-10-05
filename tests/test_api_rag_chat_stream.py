"""Integration tests for RAG Chat SSE Streaming API (ISSUE-016 / DoD-B5)."""

import json
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


def parse_sse_events(raw_text: str) -> list[tuple[str, str]]:
    """Parse raw SSE payload into a list of (event_type, data) tuples."""
    events = []
    current_event = "message"
    current_data = []

    for line in raw_text.splitlines():
        if line.startswith("event: "):
            current_event = line[len("event: ") :].strip()
        elif line.startswith("data: "):
            current_data.append(line[len("data: ") :].strip())
        elif line == "":
            if current_data or current_event != "message":
                events.append((current_event, "\n".join(current_data)))
                current_event = "message"
                current_data = []

    if current_data:
        events.append((current_event, "\n".join(current_data)))
    return events


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
    """Mock LLM provider supporting deterministic stream and fault simulation."""

    def __init__(self, fail_stream: bool = False) -> None:
        self.fail_stream = fail_stream

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
        return f"Explanation for {question.id}"

    def chat_response(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        return f"Chat response for {user_message}"

    def chat_stream(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> Iterator[str]:
        if self.fail_stream:
            raise RuntimeError("Simulated LLM streaming quota exhausted (429)")
        tokens = ["システム", "アーキテクチャの", "観点から", "解説します。"]
        yield from tokens

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

    def judge_knowledge(
        self,
        candidate: KnowledgeCandidate,
        question: ExamQuestion,
    ) -> KnowledgeVerificationResult:
        raise NotImplementedError


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
            ExamChoice(
                key="ア", text="字句解析の出力であるトークン列を入力として構文木を生成する。"
            ),
            ExamChoice(key="イ", text="ソースコードの文字ストリームから識別子を切り出す。"),
            ExamChoice(key="ウ", text="ターゲットマシンの命令セットに直接変換する。"),
            ExamChoice(key="エ", text="中間コードの最適化を行う。"),
        ],
        correct_answer="ア",
        explanation="構文解析はトークン列から構文木を構築するフェーズです。",
        keywords=["コンパイラ", "構文解析"],
    )


def sample_chunks() -> list[RetrievalChunk]:
    return [
        RetrievalChunk(
            id="chunk-qa-1",
            content="構文解析器は字句解析から渡されたトークン列を解析し構文木を構築する。",
            score=0.92,
            doc_type="exam_question",
            metadata={"question_id": "2025-SA-AM2-Q01"},
        ),
        RetrievalChunk(
            id="chunk-insight-1",
            content="コンパイラフェーズの混同（字句解析と構文解析）は頻出トラップ。",
            score=0.88,
            doc_type="learned_insight",
            metadata={"topic": "コンパイラ最適化"},
        ),
    ]


@pytest.fixture
def client_factory(tmp_path: Path):
    """Factory fixture creating test client with hermetic overrides."""

    def _create(
        initial_questions: list[ExamQuestion] | None = None,
        initial_chunks: list[RetrievalChunk] | None = None,
        fail_stream: bool = False,
    ) -> tuple[TestClient, MockQuestionRepository, MockVectorStore, MockLLMProvider]:
        db_path = tmp_path / "test_stream.db"
        history_repo = SQLitePracticeHistoryRepository(db_path=db_path)
        question_repo = MockQuestionRepository(initial_questions or [sample_question()])
        vector_store = MockVectorStore(
            initial_chunks if initial_chunks is not None else sample_chunks()
        )
        llm_provider = MockLLMProvider(fail_stream=fail_stream)

        app = create_app()
        app.dependency_overrides[get_history_repository] = lambda: history_repo
        app.dependency_overrides[get_question_repository] = lambda: question_repo
        app.dependency_overrides[get_vector_store] = lambda: vector_store
        app.dependency_overrides[get_llm_provider] = lambda: llm_provider

        client = TestClient(app)
        return client, question_repo, vector_store, llm_provider

    return _create


def test_scenario_1_chat_stream_success(client_factory):
    """シナリオ 1: 正常系 - SSE ストリーミング対話 (citation -> token -> done)."""
    client, _, _, _ = client_factory()

    response = client.post(
        "/api/rag/chat/stream",
        json={
            "question_id": "2025-SA-AM2-Q01",
            "user_message": "構文解析と字句解析の違いについて詳しく教えてください",
            "dialogue_history": [
                {"role": "user", "content": "こんにちは"},
                {"role": "assistant", "content": "こんにちは！"},
            ],
        },
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = parse_sse_events(response.text)
    event_types = [e[0] for e in events]

    # First event must be citation
    assert event_types[0] == "citation"
    citations = json.loads(events[0][1])
    assert isinstance(citations, list)
    assert len(citations) == 2
    assert citations[0]["id"] == "chunk-qa-1"

    # Subsequent events must be token
    tokens = [json.loads(e[1])["token"] for e in events if e[0] == "token"]
    assert "".join(tokens) == "システムアーキテクチャの観点から解説します。"

    # Last event must be done
    assert event_types[-1] == "done"
    done_payload = json.loads(events[-1][1])
    assert done_payload["status"] == "completed"


def test_scenario_2_chat_stream_question_not_found(client_factory):
    """シナリオ 2: 異常系 - 存在しない設問 ID の 404 ガード."""
    client, _, _, _ = client_factory()

    response = client.post(
        "/api/rag/chat/stream",
        json={
            "question_id": "NON-EXISTENT-ID",
            "user_message": "解説してください",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Question not found: NON-EXISTENT-ID"


def test_scenario_3_chat_stream_invalid_request(client_factory):
    """シナリオ 3: 異常系 - 空メッセージ等のバリデーションエラー (422)."""
    client, _, _, _ = client_factory()

    # Empty user_message
    response = client.post(
        "/api/rag/chat/stream",
        json={
            "question_id": "2025-SA-AM2-Q01",
            "user_message": "",
        },
    )
    assert response.status_code == 422

    # Missing question_id
    response_missing = client.post(
        "/api/rag/chat/stream",
        json={
            "user_message": "こんにちは",
        },
    )
    assert response_missing.status_code == 422


def test_scenario_4_chat_stream_llm_error_event(client_factory):
    """シナリオ 4: 耐障害系 - LLM 例外発生時の event: error 送出."""
    client, _, _, _ = client_factory(fail_stream=True)

    response = client.post(
        "/api/rag/chat/stream",
        json={
            "question_id": "2025-SA-AM2-Q01",
            "user_message": "この問題について質問します",
        },
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = parse_sse_events(response.text)
    event_types = [e[0] for e in events]

    assert "error" in event_types
    error_event = next(e for e in events if e[0] == "error")
    error_payload = json.loads(error_event[1])
    assert "quota exhausted" in error_payload["detail"]


def test_scenario_5_chat_stream_empty_citations(client_factory):
    """シナリオ 5: 正常系 - ベクトル検索 0 件時でも安全にストリーム成立."""
    client, _, _, _ = client_factory(initial_chunks=[])

    response = client.post(
        "/api/rag/chat/stream",
        json={
            "question_id": "2025-SA-AM2-Q01",
            "user_message": "ゼロ件検索時のテスト",
        },
    )

    assert response.status_code == 200
    events = parse_sse_events(response.text)

    # Citation event contains empty list
    assert events[0][0] == "citation"
    assert json.loads(events[0][1]) == []

    # Token and done events still succeed
    tokens = [json.loads(e[1])["token"] for e in events if e[0] == "token"]
    assert len(tokens) > 0
    assert events[-1][0] == "done"
