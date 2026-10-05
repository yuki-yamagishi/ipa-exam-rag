"""Unit tests for practice service and dojo sessions."""

import pytest

from src.application.practice_service import PracticeService
from src.domain.interfaces import IPracticeHistoryRepository, IQuestionRepository
from src.domain.models import (
    AnswerKey,
    CategoryStat,
    DojoMode,
    DojoSessionConfig,
    ExamChoice,
    ExamQuestion,
    OverallStat,
    PracticeAttempt,
    WeakQuestionStat,
)


class FakeQuestionRepository(IQuestionRepository):
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


class FakeHistoryRepository(IPracticeHistoryRepository):
    def __init__(self, attempts: list[PracticeAttempt] | None = None):
        self.attempts = attempts or []

    def record_attempt(self, attempt: PracticeAttempt) -> None:
        self.attempts.append(attempt)

    def get_attempts(
        self, question_id: str | None = None, limit: int = 100
    ) -> list[PracticeAttempt]:
        if question_id:
            return [a for a in self.attempts if a.question_id == question_id][:limit]
        return self.attempts[:limit]

    def get_attempted_question_ids(self) -> set[str]:
        return {a.question_id for a in self.attempts}

    def get_latest_attempt_per_question(self) -> dict[str, PracticeAttempt]:
        result = {}
        for a in self.attempts:
            result[a.question_id] = a
        return result

    def get_category_stats(self) -> list[CategoryStat]:
        return []

    def get_overall_stats(self) -> OverallStat:
        return OverallStat()

    def get_weak_question_stats(self, limit: int = 5) -> list[WeakQuestionStat]:
        return []

    def clear_all_attempts(self) -> None:
        self.attempts = []


def test_practice_service_submit_correct(sample_question: ExamQuestion):
    repo = FakeQuestionRepository([sample_question])
    service = PracticeService(repo)

    result = service.submit_answer(sample_question.id, AnswerKey.I)
    assert result.is_correct is True
    assert result.user_choice == AnswerKey.I
    assert result.correct_answer == AnswerKey.I


def test_practice_service_submit_incorrect(sample_question: ExamQuestion):
    repo = FakeQuestionRepository([sample_question])
    service = PracticeService(repo)

    result = service.submit_answer(sample_question.id, AnswerKey.A)
    assert result.is_correct is False
    assert result.user_choice == AnswerKey.A
    assert result.correct_answer == AnswerKey.I


def test_practice_service_question_not_found(sample_question: ExamQuestion):
    repo = FakeQuestionRepository([sample_question])
    service = PracticeService(repo)

    with pytest.raises(ValueError, match="Question NON_EXISTENT not found"):
        service.submit_answer("NON_EXISTENT", AnswerKey.A)


def test_practice_service_records_to_history(sample_question: ExamQuestion):
    q_repo = FakeQuestionRepository([sample_question])
    h_repo = FakeHistoryRepository()
    service = PracticeService(q_repo, history_repo=h_repo)

    result = service.submit_answer(
        sample_question.id,
        AnswerKey.I,
        session_id="sess-123",
        time_spent_seconds=8.5,
    )
    assert result.is_correct is True
    assert len(h_repo.attempts) == 1
    attempt = h_repo.attempts[0]
    assert attempt.session_id == "sess-123"
    assert attempt.question_id == sample_question.id
    assert attempt.is_correct is True
    assert attempt.time_spent_seconds == 8.5


def test_create_dojo_session_weak_incorrect_boundary(sample_question: ExamQuestion):
    q2 = ExamQuestion(
        id="2025-SA-AM2-Q02",
        exam_type="SA",
        year=2025,
        term="秋期",
        question_number=2,
        question_text="セキュリティ問題",
        choices=[
            ExamChoice(key=AnswerKey.A, text="選択肢ア"),
            ExamChoice(key=AnswerKey.I, text="選択肢イ"),
            ExamChoice(key=AnswerKey.U, text="選択肢ウ"),
            ExamChoice(key=AnswerKey.E, text="選択肢エ"),
        ],
        correct_answer=AnswerKey.U,
        category="情報セキュリティ",
        explanation="解説テキスト",
    )
    q_repo = FakeQuestionRepository([sample_question, q2])

    # Q1: 1st incorrect, 2nd correct -> latest is correct (Not weak)
    # Q2: 1st incorrect -> latest is incorrect (Weak)
    attempts = [
        PracticeAttempt(
            id="1",
            question_id=sample_question.id,
            question_number=1,
            category=sample_question.category,
            user_choice=AnswerKey.A,
            correct_answer=sample_question.correct_answer,
            is_correct=False,
            answered_at="2026-09-15T10:00:00Z",
        ),
        PracticeAttempt(
            id="2",
            question_id=sample_question.id,
            question_number=1,
            category=sample_question.category,
            user_choice=AnswerKey.I,
            correct_answer=sample_question.correct_answer,
            is_correct=True,
            answered_at="2026-09-15T10:05:00Z",
        ),
        PracticeAttempt(
            id="3",
            question_id=q2.id,
            question_number=2,
            category=q2.category,
            user_choice=AnswerKey.A,
            correct_answer=q2.correct_answer,
            is_correct=False,
            answered_at="2026-09-15T10:10:00Z",
        ),
    ]
    h_repo = FakeHistoryRepository(attempts)
    service = PracticeService(q_repo, history_repo=h_repo)

    # 1. Request 5 questions (boundary: only 1 weak exists, returns available 1 without error)
    config = DojoSessionConfig(mode=DojoMode.WEAK_INCORRECT, question_count=5)
    dojo_questions = service.create_dojo_session(config)
    assert len(dojo_questions) == 1
    assert dojo_questions[0].id == q2.id

    # 2. When no weak questions exist (clear all or all correct)
    h_repo.clear_all_attempts()
    empty_dojo = service.create_dojo_session(config)
    assert empty_dojo == []


def test_create_dojo_session_unanswered(sample_question: ExamQuestion):
    q2 = ExamQuestion(
        id="2025-SA-AM2-Q02",
        question_number=2,
        question_text="Q2",
        choices=[
            ExamChoice(key=AnswerKey.A, text="A"),
            ExamChoice(key=AnswerKey.I, text="B"),
            ExamChoice(key=AnswerKey.U, text="C"),
            ExamChoice(key=AnswerKey.E, text="D"),
        ],
        correct_answer=AnswerKey.A,
        category="DB",
        explanation="EXP",
    )
    q_repo = FakeQuestionRepository([sample_question, q2])

    # Attempt only Q1
    attempts = [
        PracticeAttempt(
            id="1",
            question_id=sample_question.id,
            question_number=1,
            category=sample_question.category,
            user_choice=AnswerKey.I,
            correct_answer=sample_question.correct_answer,
            is_correct=True,
        )
    ]
    h_repo = FakeHistoryRepository(attempts)
    service = PracticeService(q_repo, history_repo=h_repo)

    config = DojoSessionConfig(mode=DojoMode.UNANSWERED, question_count=5)
    unanswered = service.create_dojo_session(config)
    assert len(unanswered) == 1
    assert unanswered[0].id == q2.id
