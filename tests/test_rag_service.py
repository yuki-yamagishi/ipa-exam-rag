from typing import Any

from src.application.rag_service import RAGService
from src.domain.interfaces import ILLMProvider, IQuestionRepository, IVectorStore
from src.domain.models import (
    AnswerKey,
    DocType,
    ExamQuestion,
    KnowledgeCandidate,
    KnowledgeVerificationResult,
    RetrievalChunk,
)


class FakeVectorStore(IVectorStore):
    """Fake vector store for deterministic testing."""

    def __init__(
        self, chunks_to_return: list[RetrievalChunk] | None = None, raise_error: bool = False
    ):
        self.chunks_to_return = chunks_to_return or []
        self.raise_error = raise_error

    def setup_collection(self, collection_name: str | None = None) -> None:
        pass

    def upsert_exam_questions(
        self, questions: list[ExamQuestion], embeddings: list[list[float]]
    ) -> None:
        pass

    def upsert_insight(self, insight: Any, embedding: list[float]) -> None:
        pass

    def search_hybrid(
        self,
        query_text: str,
        query_dense_vector: list[float],
        limit: int = 5,
        filter_doc_types: list[DocType] | None = None,
    ) -> list[RetrievalChunk]:
        if self.raise_error:
            raise RuntimeError("Qdrant connection timeout simulated.")
        return self.chunks_to_return

    def find_most_similar_insight(self, query_dense_vector: list[float], threshold: float = 0.88):
        return None, 0.0

    def list_insights(self, limit: int = 50):
        return []

    def count(self) -> int:
        return len(self.chunks_to_return)


class FakeLLMForRAG(ILLMProvider):
    """Fake LLM for RAG tests."""

    def __init__(self, raise_on_generate: bool = False, raise_on_embed: bool = False):
        self.raise_on_generate = raise_on_generate
        self.raise_on_embed = raise_on_embed
        self.last_context_chunks: list[RetrievalChunk] = []

    def embed(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
        title: str | None = None,
        dimensionality: int = 768,
    ) -> list[float]:
        if self.raise_on_embed:
            raise RuntimeError("Gemini embedding quota exceeded.")
        assert task_type == "RETRIEVAL_QUERY", (
            "RAG retrieval query MUST use RETRIEVAL_QUERY task_type"
        )
        return [0.1, 0.2, 0.3, 0.4]

    def embed_batch(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        dimensionality: int = 768,
    ) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    def generate_explanation(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        if self.raise_on_generate:
            raise RuntimeError("Gemini generation API error.")
        self.last_context_chunks = context_chunks
        return f"正解は ({question.correct_answer}) です。参照コンテキスト数: {len(context_chunks)}"

    def chat_response(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        if self.raise_on_generate:
            raise RuntimeError("Gemini chat API error.")
        return f"質問「{user_message}」に対する回答です。(関連設問: {question.id})"

    def extract_knowledge_candidate(
        self, question: ExamQuestion, dialogue_history: list[dict[str, str]]
    ):
        return None

    def judge_knowledge(self, candidate: KnowledgeCandidate, question: ExamQuestion):
        return KnowledgeVerificationResult(
            is_approved=True,
            confidence_score=0.9,
            critique="",
            refined_title="",
            refined_core_concept="",
            refined_trap_analysis="",
        )


class FakeQuestionRepo(IQuestionRepository):
    def __init__(self, questions: list[ExamQuestion]):
        self.questions = questions

    def get_all_questions(self) -> list[ExamQuestion]:
        return self.questions

    def get_question_by_id(self, question_id: str) -> ExamQuestion | None:
        for q in self.questions:
            if q.id == question_id:
                return q
        return None

    def get_question_by_number(self, question_number: int) -> ExamQuestion | None:
        for q in self.questions:
            if q.question_number == question_number:
                return q
        return None


def test_rag_service_retrieve_context_normal(sample_question: ExamQuestion):
    """Scenario: RAGService retrieves context using hybrid search with RETRIEVAL_QUERY."""
    expected_chunk = RetrievalChunk(
        id="c1",
        content="サーキットブレーカーの公式シラバス解説",
        score=0.95,
        doc_type=DocType.EXAM_QUESTION,
    )
    vector_store = FakeVectorStore(chunks_to_return=[expected_chunk])
    llm_provider = FakeLLMForRAG()
    repo = FakeQuestionRepo([sample_question])

    rag_service = RAGService(vector_store, llm_provider, repo)
    chunks = rag_service.retrieve_context(query="サーキットブレーカー カスケード障害", limit=4)

    assert len(chunks) == 1
    assert chunks[0].id == "c1"
    assert "サーキットブレーカー" in chunks[0].content


def test_rag_service_generate_explanation_grounded(sample_question: ExamQuestion):
    """Scenario 1 DoD: Grounded explanation is generated using retrieved context."""
    expected_chunk = RetrievalChunk(
        id="c1",
        content="サーキットブレーカーの公式解説",
        score=0.91,
        doc_type=DocType.EXAM_QUESTION,
    )
    vector_store = FakeVectorStore(chunks_to_return=[expected_chunk])
    llm_provider = FakeLLMForRAG()
    repo = FakeQuestionRepo([sample_question])

    rag_service = RAGService(vector_store, llm_provider, repo)
    explanation = rag_service.generate_explanation(sample_question, AnswerKey.I)

    assert "正解は (イ) です" in explanation
    assert "参照コンテキスト数: 1" in explanation
    assert len(llm_provider.last_context_chunks) == 1


def test_rag_service_generate_explanation_fallback_on_llm_error(sample_question: ExamQuestion):
    """Scenario: Graceful degradation to official explanation when LLM API fails."""
    vector_store = FakeVectorStore()
    llm_provider = FakeLLMForRAG(raise_on_generate=True)
    repo = FakeQuestionRepo([sample_question])

    rag_service = RAGService(vector_store, llm_provider, repo)
    explanation = rag_service.generate_explanation(sample_question, AnswerKey.A)

    assert "【公式正解】: (イ)" in explanation
    assert "【公式解説】:" in explanation
    assert sample_question.explanation in explanation


def test_rag_service_generate_explanation_fallback_on_vector_error(sample_question: ExamQuestion):
    """Scenario: System does NOT crash when Qdrant search encounters connection error."""
    vector_store = FakeVectorStore(raise_error=True)
    llm_provider = FakeLLMForRAG()
    repo = FakeQuestionRepo([sample_question])

    rag_service = RAGService(vector_store, llm_provider, repo)
    # Must not raise exception, retrieve_context handles error safely
    explanation = rag_service.generate_explanation(sample_question, AnswerKey.I)

    assert "正解は (イ) です" in explanation
    assert "参照コンテキスト数: 0" in explanation


def test_rag_service_chat_discuss_normal(sample_question: ExamQuestion):
    """Scenario: Interactive discussion chat generates grounded response."""
    vector_store = FakeVectorStore()
    llm_provider = FakeLLMForRAG()
    repo = FakeQuestionRepo([sample_question])

    rag_service = RAGService(vector_store, llm_provider, repo)
    reply = rag_service.chat_discuss(
        question=sample_question,
        dialogue_history=[],
        user_message="なぜウが不正解なのか教えてください",
    )

    assert "質問「なぜウが不正解なのか教えてください」に対する回答です" in reply
