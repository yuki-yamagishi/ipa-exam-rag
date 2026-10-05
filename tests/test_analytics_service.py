"""Unit tests for AnalyticsService."""

from src.application.analytics_service import AnalyticsService
from src.domain.interfaces import IPracticeHistoryRepository, IQuestionRepository
from src.domain.models import (
    AnswerKey,
    CategoryStat,
    ExamQuestion,
    OverallStat,
    PracticeAttempt,
    WeakQuestionStat,
)


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
        cats: dict[str, list[PracticeAttempt]] = {}
        for a in self.attempts:
            cats.setdefault(a.category, []).append(a)
        stats = []
        for cat, atts in cats.items():
            total = len(atts)
            correct = sum(1 for a in atts if a.is_correct)
            stats.append(
                CategoryStat(
                    category=cat,
                    total_attempts=total,
                    correct_attempts=correct,
                    accuracy_rate=round(correct / total, 4) if total > 0 else 0.0,
                )
            )
        return stats

    def get_overall_stats(self) -> OverallStat:
        if not self.attempts:
            return OverallStat()
        total = len(self.attempts)
        correct = sum(1 for a in self.attempts if a.is_correct)
        distinct_q = len({a.question_id for a in self.attempts})
        distinct_s = len({a.session_id for a in self.attempts if a.session_id})
        return OverallStat(
            total_attempts=total,
            correct_attempts=correct,
            accuracy_rate=round(correct / total, 4) if total > 0 else 0.0,
            distinct_questions_attempted=distinct_q,
            total_sessions=distinct_s,
        )

    def get_weak_question_stats(self, limit: int = 5) -> list[WeakQuestionStat]:
        latest_map = self.get_latest_attempt_per_question()
        stats = []
        for q_id, latest in latest_map.items():
            q_attempts = [a for a in self.attempts if a.question_id == q_id]
            inc_count = sum(1 for a in q_attempts if not a.is_correct)
            stats.append(
                WeakQuestionStat(
                    question_id=q_id,
                    question_number=latest.question_number,
                    category=latest.category,
                    question_text="",
                    total_attempts=len(q_attempts),
                    incorrect_count=inc_count,
                    latest_is_correct=latest.is_correct,
                )
            )
        return sorted(stats, key=lambda s: (s.latest_is_correct, -s.incorrect_count))[:limit]

    def clear_all_attempts(self) -> None:
        self.attempts = []


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


def test_analytics_dashboard_and_categories():
    attempts = [
        PracticeAttempt(
            id="1",
            question_id="Q1",
            question_number=1,
            category="アーキテクチャ",
            user_choice=AnswerKey.I,
            correct_answer=AnswerKey.I,
            is_correct=True,
            answered_at="2026-09-15T10:00:00Z",
        ),
        PracticeAttempt(
            id="2",
            question_id="Q2",
            question_number=2,
            category="セキュリティ",
            user_choice=AnswerKey.A,
            correct_answer=AnswerKey.I,
            is_correct=False,
            answered_at="2026-09-15T10:05:00Z",
        ),
    ]
    history_repo = FakeHistoryRepository(attempts)
    service = AnalyticsService(history_repo)

    overall = service.get_overall_dashboard()
    assert overall.total_attempts == 2
    assert overall.correct_attempts == 1
    assert overall.accuracy_rate == 0.5

    cat_stats = service.get_category_performance()
    assert len(cat_stats) == 2

    weak_cats = service.get_weakest_categories(max_accuracy=0.6)
    assert len(weak_cats) == 1
    assert weak_cats[0].category == "セキュリティ"


def test_analytics_weak_question_ids_latest_attempt_logic():
    # Q1: 1st incorrect, 2nd correct -> latest is correct (NOT weak)
    # Q2: 1st incorrect -> latest is incorrect (IS weak)
    attempts = [
        PracticeAttempt(
            id="1",
            question_id="Q1",
            question_number=1,
            category="アーキテクチャ",
            user_choice=AnswerKey.A,
            correct_answer=AnswerKey.I,
            is_correct=False,
            answered_at="2026-09-15T10:00:00Z",
        ),
        PracticeAttempt(
            id="2",
            question_id="Q1",
            question_number=1,
            category="アーキテクチャ",
            user_choice=AnswerKey.I,
            correct_answer=AnswerKey.I,
            is_correct=True,
            answered_at="2026-09-15T10:10:00Z",
        ),
        PracticeAttempt(
            id="3",
            question_id="Q2",
            question_number=2,
            category="セキュリティ",
            user_choice=AnswerKey.U,
            correct_answer=AnswerKey.E,
            is_correct=False,
            answered_at="2026-09-15T10:20:00Z",
        ),
    ]
    history_repo = FakeHistoryRepository(attempts)
    service = AnalyticsService(history_repo)

    weak_ids = service.get_weak_question_ids()
    assert "Q2" in weak_ids
    assert "Q1" not in weak_ids


def test_analytics_empty_data():
    history_repo = FakeHistoryRepository([])
    service = AnalyticsService(history_repo)

    overall = service.get_overall_dashboard()
    assert overall.total_attempts == 0
    assert overall.accuracy_rate == 0.0

    assert service.get_category_performance() == []
    assert service.get_weakest_categories() == []
    assert service.get_weak_question_ids() == []
    assert service.get_weak_questions() == []
