"""Practice service handling question attempts, scoring, and continuous dojo sessions."""

import random
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel

from src.domain.interfaces import IPracticeHistoryRepository, IQuestionRepository
from src.domain.models import (
    AnswerKey,
    DojoMode,
    DojoSessionConfig,
    DojoSessionState,
    ExamChoice,
    ExamQuestion,
    PracticeAttempt,
)


class PracticeResult(BaseModel):
    """Result of a question practice attempt."""

    question_id: str
    question_number: int
    user_choice: AnswerKey
    correct_answer: AnswerKey
    is_correct: bool
    selected_choice: ExamChoice | None
    correct_choice: ExamChoice | None
    category: str
    attempt_id: str | None = None


class PracticeService:
    """Application service for practicing exam questions and running dojo sessions."""

    def __init__(
        self,
        question_repo: IQuestionRepository,
        history_repo: IPracticeHistoryRepository | None = None,
    ):
        self.question_repo = question_repo
        self.history_repo = history_repo

    def get_question_list(self) -> list[ExamQuestion]:
        """Return all available practice questions."""
        return self.question_repo.get_all_questions()

    def get_question(self, question_id: str) -> ExamQuestion | None:
        """Find question by ID."""
        return self.question_repo.get_question_by_id(question_id)

    def submit_answer(
        self,
        question_id: str,
        choice_key: AnswerKey,
        session_id: str | None = None,
        time_spent_seconds: float = 0.0,
        user_email: str = "",
    ) -> PracticeResult:
        """Evaluate user choice, persist attempt to database, and return scoring result."""
        question = self.question_repo.get_question_by_id(question_id)
        if not question:
            raise ValueError(f"Question {question_id} not found.")

        is_correct = choice_key == question.correct_answer
        attempt_id = str(uuid.uuid4())

        if self.history_repo:
            attempt = PracticeAttempt(
                id=attempt_id,
                session_id=session_id,
                question_id=question.id,
                exam_type=question.exam_type,
                year=question.year,
                term=question.term,
                question_number=question.question_number,
                category=question.category,
                user_choice=choice_key,
                correct_answer=question.correct_answer,
                is_correct=is_correct,
                time_spent_seconds=time_spent_seconds,
                user_email=user_email,
                answered_at=datetime.now(UTC).isoformat(),
            )
            self.history_repo.record_attempt(attempt)

        return PracticeResult(
            question_id=question.id,
            question_number=question.question_number,
            user_choice=choice_key,
            correct_answer=question.correct_answer,
            is_correct=is_correct,
            selected_choice=question.get_choice(choice_key),
            correct_choice=question.get_choice(question.correct_answer),
            category=question.category,
            attempt_id=attempt_id,
        )

    def create_dojo_session(self, config: DojoSessionConfig) -> list[ExamQuestion]:
        """Build an ordered queue of questions for a continuous practice dojo session.

        Guarantees:
        - WEAK_INCORRECT filters questions whose latest attempt was incorrect.
        - If matching question count is less than requested, returns all available matching questions.
        - If matching question count is 0, safely returns empty list [] without error.
        """
        all_questions = self.question_repo.get_all_questions()
        if config.year is not None:
            all_questions = [q for q in all_questions if q.year == config.year]

        if config.mode == DojoMode.ALL:
            candidates = list(all_questions)

        elif config.mode == DojoMode.CATEGORY:
            if config.category:
                candidates = [q for q in all_questions if q.category == config.category]
            else:
                candidates = list(all_questions)

        elif config.mode == DojoMode.WEAK_INCORRECT:
            if self.history_repo:
                latest_map = self.history_repo.get_latest_attempt_per_question()
                weak_qids = {qid for qid, attempt in latest_map.items() if not attempt.is_correct}
                candidates = [q for q in all_questions if q.id in weak_qids]
            else:
                candidates = []

        elif config.mode == DojoMode.UNANSWERED:
            if self.history_repo:
                attempted_qids = self.history_repo.get_attempted_question_ids()
                candidates = [q for q in all_questions if q.id not in attempted_qids]
            else:
                candidates = list(all_questions)
        else:
            candidates = list(all_questions)

        if config.shuffle:
            random.shuffle(candidates)

        return candidates[: config.question_count]

    def save_session_progress(self, session: DojoSessionState) -> None:
        """Persist or update the progress of an active dojo practice session."""
        session.updated_at = datetime.now(UTC).isoformat()
        if self.history_repo:
            self.history_repo.save_session_state(session)

    def get_resumable_session(self, user_email: str = "") -> DojoSessionState | None:
        """Fetch the most recent uncompleted dojo session for a user if exists."""
        if not self.history_repo:
            return None
        return self.history_repo.get_active_session(user_email=user_email)

    def get_active_resumable_session(
        self, user_email: str = ""
    ) -> tuple[DojoSessionState, list[ExamQuestion]] | None:
        """Fetch active uncompleted session and reconstruct its question queue in a single lookup."""
        if not self.history_repo:
            return None
        session = self.history_repo.get_active_session(user_email=user_email)
        if not session:
            return None

        question_map = {q.id: q for q in self.question_repo.get_all_questions()}
        queue = [question_map[qid] for qid in session.question_ids if qid in question_map]
        if not queue:
            return None

        return session, queue

    def resume_dojo_session(
        self, session_id: str, user_email: str = ""
    ) -> tuple[DojoSessionState, list[ExamQuestion]] | None:
        """Restore active session state and reconstruct question queue in original order."""
        active = self.get_active_resumable_session(user_email=user_email)
        if not active:
            return None
        session, queue = active
        if session.session_id != session_id:
            return None

        return session, queue

    def complete_session(self, session_id: str) -> None:
        """Mark a dojo practice session as completed."""
        if self.history_repo:
            self.history_repo.mark_session_completed(session_id)

    def get_session_by_id(self, session_id: str) -> DojoSessionState | None:
        """Fetch a specific dojo session by session ID."""
        if not self.history_repo:
            return None
        return self.history_repo.get_session_by_id(session_id)

    def abandon_session(self, session_id: str) -> None:
        """Permanently abandon or discard an incomplete dojo practice session."""
        if self.history_repo:
            self.history_repo.delete_session(session_id)
