"""Domain models for IPA Exam RAG."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnswerKey(StrEnum):
    """IPA Exam 4-choice keys."""

    A = "ア"
    I = "イ"
    U = "ウ"
    E = "エ"


class DocType(StrEnum):
    """Vector database document types."""

    EXAM_QUESTION = "exam_question"
    LEARNED_INSIGHT = "learned_insight"
    SYLLABUS = "syllabus"


class ExamChoice(BaseModel):
    """Multiple choice item for an IPA exam question."""

    key: AnswerKey
    text: str

    model_config = ConfigDict(frozen=True)


class ExamQuestion(BaseModel):
    """Exam question entity."""

    id: str = Field(description="Unique question identifier, e.g. 2025-SA-AM2-Q01")
    exam_type: str = Field(default="SA", description="Examination category, e.g. SA")
    year: int = Field(default=2025, description="Exam year")
    term: str = Field(default="秋期", description="Exam term, e.g. 春期, 秋期")
    question_number: int = Field(ge=1, le=25, description="Question number in exam (1-25)")
    question_text: str = Field(description="Question body text")
    choices: list[ExamChoice] = Field(
        min_length=4, max_length=4, description="Four choices (ア, イ, ウ, エ)"
    )
    correct_answer: AnswerKey = Field(description="Official correct answer key")
    category: str = Field(description="Syllabus/Domain category, e.g. システムアーキテクチャ")
    explanation: str = Field(description="Official or baseline technical explanation")
    keywords: list[str] = Field(default_factory=list, description="Associated technical keywords")

    def get_choice(self, key: AnswerKey) -> ExamChoice | None:
        """Find choice by key."""
        for c in self.choices:
            if c.key == key:
                return c
        return None

    def format_full_text(self) -> str:
        """Format complete question with choices for embedding/display."""
        choices_str = "\n".join([f"({c.key}) {c.text}" for c in self.choices])
        return f"【問題 {self.question_number}】({self.category})\n{self.question_text}\n\n[選択肢]\n{choices_str}"


class KnowledgeCandidate(BaseModel):
    """Raw insight extracted from interactive dialogue before judge review."""

    source_question_id: str = Field(description="Associated question ID")
    title: str = Field(description="Concise insight title")
    core_concept: str = Field(description="Core technical principle explained")
    trap_analysis: str = Field(description="Why wrong choices are tempting or incorrect")
    practical_takeaway: str = Field(description="Practical architecture design insight")
    dialogue_context: str = Field(description="Summary of user dialogue triggering this insight")
    proposed_tags: list[str] = Field(default_factory=list, description="Tags proposed by extractor")


class KnowledgeCandidateList(BaseModel):
    """Container for multiple extracted candidate insights."""

    candidates: list[KnowledgeCandidate] = Field(
        default_factory=list,
        description="List of distinct technical candidate insights extracted from dialogue",
    )


class KnowledgeVerificationResult(BaseModel):
    """Structured evaluation output produced by the Judge Agent."""

    is_approved: bool = Field(
        description="Whether the insight is factually sound and approved for indexing"
    )
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence score (0.0 - 1.0)")
    critique: str = Field(description="Detailed factual critique and rationale for decision")
    refined_title: str = Field(description="Refined and standardized title")
    refined_core_concept: str = Field(description="Fact-checked core concept description")
    refined_trap_analysis: str = Field(description="Fact-checked trap analysis")
    tags: list[str] = Field(default_factory=list, description="Standardized topic tags")


class LearnedInsight(BaseModel):
    """Verified and indexed insight stored in knowledge base."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Unique insight identifier UUID or hash")
    source_question_id: str = Field(description="Origin question ID")
    title: str = Field(description="Insight title")
    core_concept: str = Field(description="Fact-checked core principle")
    trap_analysis: str = Field(description="Trap and distractors analysis")
    practical_takeaway: str = Field(description="Architecture guideline")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Verification confidence score")
    is_verified: bool = Field(default=True, description="Verification gate status")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str | None = None

    def format_document_text(self) -> str:
        """Format representation for RETRIEVAL_DOCUMENT embedding."""
        tags_str = ", ".join(self.tags)
        return (
            f"【学習知見】{self.title} (対象設問: {self.source_question_id})\n"
            f"[タグ]: {tags_str}\n"
            f"[核心概念]: {self.core_concept}\n"
            f"[誤答・トラップ解説]: {self.trap_analysis}\n"
            f"[設計・実務指針]: {self.practical_takeaway}"
        )


class RetrievalChunk(BaseModel):
    """Retrieved search result chunk from Qdrant."""

    id: str
    content: str
    score: float
    doc_type: DocType
    metadata: dict[str, Any] = Field(default_factory=dict)


class DojoMode(StrEnum):
    """Practice dojo question selection modes."""

    ALL = "all"
    CATEGORY = "category"
    WEAK_INCORRECT = "weak_incorrect"
    UNANSWERED = "unanswered"


class DojoSessionConfig(BaseModel):
    """Configuration for a continuous dojo practice session."""

    mode: DojoMode = DojoMode.ALL
    year: int | None = None
    category: str | None = None
    question_count: int = 5
    shuffle: bool = False
    user_email: str = ""


class DojoSessionState(BaseModel):
    """Persistent state of an active or interrupted dojo practice session."""

    session_id: str
    user_email: str = ""
    mode: DojoMode = DojoMode.ALL
    year: int | None = None
    category: str | None = None
    question_count: int = 5
    shuffle: bool = False
    question_ids: list[str] = Field(default_factory=list)
    current_index: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    is_completed: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class PracticeAttempt(BaseModel):
    """Persistent question practice attempt record."""

    id: str
    session_id: str | None = None
    question_id: str
    exam_type: str = "SA"
    year: int = 2025
    term: str = "秋期"
    question_number: int
    category: str
    user_choice: AnswerKey
    correct_answer: AnswerKey
    is_correct: bool
    time_spent_seconds: float = 0.0
    user_email: str = ""
    answered_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class CategoryStat(BaseModel):
    """Statistical summary per exam category."""

    category: str
    total_attempts: int
    correct_attempts: int
    accuracy_rate: float


class OverallStat(BaseModel):
    """Overall learning summary metrics."""

    total_attempts: int = 0
    correct_attempts: int = 0
    accuracy_rate: float = 0.0
    distinct_questions_attempted: int = 0
    total_sessions: int = 0


class WeakQuestionStat(BaseModel):
    """Statistics for a question identifying student weakness."""

    question_id: str
    question_number: int
    category: str
    question_text: str
    total_attempts: int
    incorrect_count: int
    latest_is_correct: bool
