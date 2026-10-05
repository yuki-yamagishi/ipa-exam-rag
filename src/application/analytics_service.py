"""Analytics service analyzing student performance, category mastery, and weak points."""

import logging

from src.domain.interfaces import IPracticeHistoryRepository, IQuestionRepository
from src.domain.models import (
    CategoryStat,
    OverallStat,
    PracticeAttempt,
    WeakQuestionStat,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Application service providing performance analytics and weak point diagnosis."""

    def __init__(
        self,
        history_repo: IPracticeHistoryRepository,
        question_repo: IQuestionRepository | None = None,
    ):
        self.history_repo = history_repo
        self.question_repo = question_repo

    def get_overall_dashboard(self) -> OverallStat:
        """Return high-level summary metrics (attempts, correct count, accuracy, sessions)."""
        return self.history_repo.get_overall_stats()

    def get_category_performance(self) -> list[CategoryStat]:
        """Return category performance stats sorted by volume of attempts."""
        return self.history_repo.get_category_stats()

    def get_weakest_categories(self, max_accuracy: float = 0.6) -> list[CategoryStat]:
        """Return categories where accuracy is below the given threshold."""
        all_stats = self.get_category_performance()
        return [s for s in all_stats if s.total_attempts > 0 and s.accuracy_rate < max_accuracy]

    def get_weak_question_ids(self) -> list[str]:
        """Return list of question IDs whose latest attempt was incorrect.

        Following DoR specification: evaluated based on the student's latest attempt per question.
        """
        latest_map = self.history_repo.get_latest_attempt_per_question()
        return [q_id for q_id, attempt in latest_map.items() if not attempt.is_correct]

    def get_weak_questions(self, limit: int = 5) -> list[WeakQuestionStat]:
        """Return weak questions enriched with original question body text."""
        weak_stats = self.history_repo.get_weak_question_stats(limit=limit)

        if not self.question_repo:
            return weak_stats

        enriched_stats: list[WeakQuestionStat] = []
        for item in weak_stats:
            q = self.question_repo.get_question_by_id(item.question_id)
            if q:
                enriched_stats.append(
                    item.model_copy(
                        update={
                            "question_text": q.question_text,
                            "question_number": q.question_number,
                            "category": q.category,
                        }
                    )
                )
            else:
                enriched_stats.append(item)

        return enriched_stats

    def get_recent_attempts(self, limit: int = 20) -> list[PracticeAttempt]:
        """Return the most recent practice attempts."""
        return self.history_repo.get_attempts(limit=limit)
