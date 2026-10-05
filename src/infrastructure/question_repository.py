"""Question repository loading seed datasets from JSON files or directory."""

import json
import logging
from pathlib import Path

from src.domain.interfaces import IQuestionRepository
from src.domain.models import ExamQuestion

logger = logging.getLogger(__name__)

DEFAULT_SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seeds"


class LocalQuestionRepository(IQuestionRepository):
    """Local JSON based question repository supporting single file or directory scanning."""

    def __init__(
        self,
        seed_path: Path | str | None = None,
        seed_file_path: Path | str | None = None,
    ):
        target = seed_path or seed_file_path or DEFAULT_SEEDS_DIR
        self.target_path = Path(target)
        self._questions: list[ExamQuestion] = []
        self._load()

    def _load(self) -> None:
        if not self.target_path.exists():
            logger.warning("Seed path not found at %s. Questions list is empty.", self.target_path)
            self._questions = []
            return

        json_files: list[Path] = []
        if self.target_path.is_dir():
            json_files = sorted(self.target_path.glob("*.json"))
        elif self.target_path.is_file():
            json_files = [self.target_path]

        loaded_questions: list[ExamQuestion] = []
        seen_ids: set[str] = set()

        for file_path in json_files:
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        q = ExamQuestion.model_validate(item)
                        if q.id not in seen_ids:
                            seen_ids.add(q.id)
                            loaded_questions.append(q)
                        else:
                            logger.warning(
                                "Duplicate question ID skipped: %s in %s", q.id, file_path
                            )
                logger.info(
                    "Loaded questions from %s (running total: %d)", file_path, len(loaded_questions)
                )
            except Exception as e:
                logger.error("Failed to parse seed questions from %s: %s", file_path, e)

        # Sort primarily by year descending, secondarily by question number ascending
        self._questions = sorted(loaded_questions, key=lambda q: (-q.year, q.question_number))
        logger.info(
            "LocalQuestionRepository initialized with %d total questions across %d years.",
            len(self._questions),
            len(self.get_available_years()),
        )

    def get_all_questions(self) -> list[ExamQuestion]:
        """Return all questions sorted by year descending and question number ascending."""
        return list(self._questions)

    def get_question_by_id(self, question_id: str) -> ExamQuestion | None:
        """Find question by ID (e.g. 2025-SA-AM2-Q01)."""
        for q in self._questions:
            if q.id == question_id:
                return q
        return None

    def get_question_by_number(self, question_number: int) -> ExamQuestion | None:
        """Find question by number (defaults to most recent year)."""
        for q in self._questions:
            if q.question_number == question_number:
                return q
        return None

    def get_available_years(self) -> list[int]:
        """Return unique exam years available in descending order."""
        years = {q.year for q in self._questions}
        return sorted(years, reverse=True)

    def get_questions_by_year(self, year: int) -> list[ExamQuestion]:
        """Return all questions belonging to a specific exam year, sorted by question number."""
        matched = [q for q in self._questions if q.year == year]
        return sorted(matched, key=lambda q: q.question_number)
