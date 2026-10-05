"""Domain repository and provider interfaces (Protocols)."""

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from src.domain.models import (
    AnswerKey,
    CategoryStat,
    DocType,
    DojoSessionState,
    ExamQuestion,
    KnowledgeCandidate,
    KnowledgeVerificationResult,
    LearnedInsight,
    OverallStat,
    PracticeAttempt,
    RetrievalChunk,
    WeakQuestionStat,
)


@runtime_checkable
class IVectorStore(Protocol):
    """Vector database operations interface."""

    def setup_collection(self, collection_name: str | None = None) -> None:
        """Create or ensure vector collection with required payload indexes."""
        ...

    def upsert_exam_questions(
        self, questions: list[ExamQuestion], embeddings: list[list[float]]
    ) -> None:
        """Store exam questions with embeddings and metadata payload."""
        ...

    def upsert_insight(self, insight: LearnedInsight, embedding: list[float]) -> None:
        """Store or update a learned insight."""
        ...

    def search_hybrid(
        self,
        query_text: str,
        query_dense_vector: list[float],
        limit: int = 5,
        filter_doc_types: list[DocType] | None = None,
    ) -> list[RetrievalChunk]:
        """Perform hybrid search (Dense + Sparse/Full-text with RRF)."""
        ...

    def find_most_similar_insight(
        self, query_dense_vector: list[float], threshold: float = 0.88
    ) -> tuple[LearnedInsight | None, float]:
        """Find the most similar existing insight to prevent duplicates."""
        ...

    def list_insights(self, limit: int = 50) -> list[LearnedInsight]:
        """List all verified insights currently stored."""
        ...

    def count(self) -> int:
        """Return the total number of points/records in the vector collection."""
        ...


@runtime_checkable
class ILLMProvider(Protocol):
    """Google Gemini LLM and Embedding provider interface."""

    def embed(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
        title: str | None = None,
        dimensionality: int = 768,
    ) -> list[float]:
        """Generate embedding vector with explicit task type and MRL dimensionality."""
        ...

    def embed_batch(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        dimensionality: int = 768,
    ) -> list[list[float]]:
        """Batch embedding calculation."""
        ...

    def generate_explanation(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        """Generate grounded technical explanation with retrieved context."""
        ...

    def chat_response(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        """Generate interactive conversational response based on grounded context."""
        ...

    def chat_stream(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> Iterator[str]:
        """Generate streaming interactive conversational response chunks."""
        ...

    def extract_knowledge_candidate(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> KnowledgeCandidate | None:
        """Extract candidate architectural and trap insight from dialogue."""
        ...

    def extract_knowledge_candidates(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> list[KnowledgeCandidate]:
        """Extract multiple distinct technical insights from dialogue."""
        ...

    def judge_knowledge(
        self,
        candidate: KnowledgeCandidate,
        question: ExamQuestion,
    ) -> KnowledgeVerificationResult:
        """Evaluate candidate with strict Pydantic structured output schema."""
        ...

    def update_api_key(self, api_key: str) -> None:
        """Dynamically update Gemini API key."""
        ...


@runtime_checkable
class IQuestionRepository(Protocol):
    """Question dataset repository interface."""

    def get_all_questions(self) -> list[ExamQuestion]:
        """Return all available questions."""
        ...

    def get_question_by_id(self, question_id: str) -> ExamQuestion | None:
        """Find question by ID (e.g. 2025-SA-AM2-Q01)."""
        ...

    def get_question_by_number(self, question_number: int) -> ExamQuestion | None:
        """Find question by number (1-25)."""
        ...

    def get_available_years(self) -> list[int]:
        """Return unique exam years available in descending order."""
        ...

    def get_questions_by_year(self, year: int) -> list[ExamQuestion]:
        """Return all questions belonging to a specific exam year."""
        ...


@runtime_checkable
class IPracticeHistoryRepository(Protocol):
    """Repository for persisting and querying question practice attempts."""

    def record_attempt(self, attempt: PracticeAttempt) -> None:
        """Persist a single practice attempt."""
        ...

    def get_attempts(
        self, question_id: str | None = None, limit: int = 100
    ) -> list[PracticeAttempt]:
        """Fetch attempt history, optionally filtered by question ID."""
        ...

    def get_attempted_question_ids(self) -> set[str]:
        """Return the set of unique question IDs that have been attempted."""
        ...

    def get_latest_attempt_per_question(self) -> dict[str, PracticeAttempt]:
        """Return a mapping of question_id to the most recent PracticeAttempt."""
        ...

    def get_category_stats(self) -> list[CategoryStat]:
        """Return aggregated statistics grouped by question category."""
        ...

    def get_overall_stats(self) -> OverallStat:
        """Return overall aggregate statistics across all attempts."""
        ...

    def get_weak_question_stats(self, limit: int = 5) -> list[WeakQuestionStat]:
        """Return questions with highest incorrect counts or latest incorrect attempts."""
        ...

    def clear_all_attempts(self) -> None:
        """Clear all practice attempt records (for testing or reset)."""
        ...

    def clear_all(self) -> None:
        """Clear all practice attempts and dojo sessions."""
        ...

    def save_session_state(self, session: DojoSessionState) -> None:
        """Persist or update an active dojo practice session."""
        ...

    def get_active_session(self, user_email: str = "") -> DojoSessionState | None:
        """Fetch the most recent uncompleted dojo session for a user if exists."""
        ...

    def get_session_by_id(self, session_id: str) -> DojoSessionState | None:
        """Fetch a specific dojo session by session ID."""
        ...

    def mark_session_completed(self, session_id: str) -> None:
        """Mark a dojo session as completed."""
        ...

    def delete_session(self, session_id: str) -> None:
        """Permanently remove or abandon a dojo session."""
        ...
