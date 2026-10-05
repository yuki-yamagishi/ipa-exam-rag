"""Unit tests for LocalQuestionRepository and 5-year (2021-2025) SA AM2 seed dataset."""

from pathlib import Path

from src.domain.models import AnswerKey
from src.infrastructure.question_repository import LocalQuestionRepository


def test_local_question_repository_loads_all_125_questions():
    """Verify that all 125 questions from 2021-2025 SA AM2 seed JSON files are loaded successfully."""
    repo = LocalQuestionRepository()
    questions = repo.get_all_questions()

    # Must contain exactly 125 questions (5 years * 25 questions)
    assert len(questions) == 125, f"Expected 125 questions, got {len(questions)}"

    # Check available years
    years = repo.get_available_years()
    assert years == [2025, 2024, 2023, 2022, 2021]

    # Verify each year has exactly 25 questions numbered 1 to 25
    valid_keys = {AnswerKey.A, AnswerKey.I, AnswerKey.U, AnswerKey.E}
    for year in years:
        year_questions = repo.get_questions_by_year(year)
        assert len(year_questions) == 25, (
            f"Expected 25 questions for {year}, got {len(year_questions)}"
        )
        numbers = [q.question_number for q in year_questions]
        assert numbers == list(range(1, 26))

        for q in year_questions:
            assert q.year == year
            assert q.exam_type == "SA"
            assert q.id == f"{year}-SA-AM2-Q{q.question_number:02d}"
            assert len(q.choices) == 4
            assert q.correct_answer in valid_keys
            assert len(q.question_text) > 10
            assert len(q.explanation) > 10
            assert len(q.keywords) > 0


def test_local_question_repository_single_file_backward_compatibility():
    """Verify backward compatibility when passing a single JSON file path."""
    single_file = Path("data/seeds/sa_2025_am2.json")
    repo = LocalQuestionRepository(seed_file_path=single_file)
    questions = repo.get_all_questions()

    assert len(questions) == 25
    assert repo.get_available_years() == [2025]
    assert all(q.year == 2025 for q in questions)


def test_local_question_repository_get_by_id_and_number():
    """Test lookup by question ID and number."""
    repo = LocalQuestionRepository()

    # Get by number defaults to latest year (2025)
    q1 = repo.get_question_by_number(1)
    assert q1 is not None
    assert q1.question_number == 1
    assert q1.year == 2025
    assert "DFD" in q1.question_text

    # Lookup by specific IDs across different years
    q_2025_25 = repo.get_question_by_id("2025-SA-AM2-Q25")
    assert q_2025_25 is not None
    assert q_2025_25.year == 2025
    assert q_2025_25.question_number == 25

    q_2021_01 = repo.get_question_by_id("2021-SA-AM2-Q01")
    assert q_2021_01 is not None
    assert q_2021_01.year == 2021
    assert q_2021_01.question_number == 1
    assert "アシュアランスケース" in q_2021_01.question_text

    q_2023_10 = repo.get_question_by_id("2023-SA-AM2-Q10")
    assert q_2023_10 is not None
    assert q_2023_10.year == 2023
    assert q_2023_10.question_number == 10

    # Non-existent
    assert repo.get_question_by_number(999) is None
    assert repo.get_question_by_id("NON_EXISTENT") is None


def test_local_question_repository_handles_missing_file(tmp_path: Path):
    """Test graceful handling when seed file path does not exist."""
    missing_file = tmp_path / "non_existent.json"
    repo = LocalQuestionRepository(seed_file_path=missing_file)
    assert repo.get_all_questions() == []
