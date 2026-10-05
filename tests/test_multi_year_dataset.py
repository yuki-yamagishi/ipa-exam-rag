"""Integration and unit tests for 5-year multi-year dataset, year-specific dojo, and 3-axis browse filtering."""

from src.application.practice_service import PracticeService
from src.domain.models import AnswerKey, DojoMode, DojoSessionConfig
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.infrastructure.question_repository import LocalQuestionRepository


def test_multi_year_dataset_integrity():
    """Verify integrity of the entire 5-year (2021-2025) 125-question dataset."""
    repo = LocalQuestionRepository()
    all_questions = repo.get_all_questions()

    assert len(all_questions) == 125, f"Expected 125 questions, got {len(all_questions)}"

    # All IDs must be unique
    all_ids = [q.id for q in all_questions]
    assert len(all_ids) == len(set(all_ids)), "Duplicate question IDs detected in dataset!"

    # Available years must be exactly 2025 down to 2021
    years = repo.get_available_years()
    assert years == [2025, 2024, 2023, 2022, 2021]

    # Every question must have complete valid schema
    valid_answer_keys = {AnswerKey.A, AnswerKey.I, AnswerKey.U, AnswerKey.E}
    for q in all_questions:
        assert q.year in {2021, 2022, 2023, 2024, 2025}
        expected_term = "秋期" if q.year <= 2022 else "春期"
        assert q.term == expected_term, f"Question {q.id} year {q.year} expected term {expected_term}, got {q.term}"
        assert q.exam_type == "SA"
        assert 1 <= q.question_number <= 25
        assert len(q.choices) == 4
        choice_keys = {c.key for c in q.choices}
        assert choice_keys == valid_answer_keys
        assert q.correct_answer in valid_answer_keys
        assert len(q.question_text) >= 10
        assert len(q.explanation) > 10
        assert len(q.keywords) >= 1
        assert len(q.category) > 0


def test_multi_year_question_sorting_order():
    """Verify get_all_questions() is strictly sorted by year DESC then question_number ASC."""
    repo = LocalQuestionRepository()
    questions = repo.get_all_questions()

    for i in range(len(questions) - 1):
        curr = questions[i]
        nxt = questions[i + 1]
        if curr.year == nxt.year:
            assert curr.question_number < nxt.question_number, (
                f"Question numbering not ascending within year {curr.year}: "
                f"Q{curr.question_number} followed by Q{nxt.question_number}"
            )
        else:
            assert curr.year > nxt.year, f"Years not descending: {curr.year} followed by {nxt.year}"


def test_dojo_session_with_year_filter():
    """Verify DojoSessionConfig year filtering in PracticeService."""
    repo = LocalQuestionRepository()
    service = PracticeService(question_repo=repo)

    # 1. Year filter: 2024 only, 10 questions
    cfg_2024 = DojoSessionConfig(year=2024, question_count=10, shuffle=False)
    q_2024 = service.create_dojo_session(cfg_2024)
    assert len(q_2024) == 10
    assert all(q.year == 2024 for q in q_2024)
    assert [q.question_number for q in q_2024] == list(range(1, 11))

    # 2. Year filter: 2021 all 25 questions
    cfg_2021 = DojoSessionConfig(year=2021, question_count=25, shuffle=False)
    q_2021 = service.create_dojo_session(cfg_2021)
    assert len(q_2021) == 25
    assert all(q.year == 2021 for q in q_2021)

    # 3. All years (year=None), 50 questions
    cfg_all = DojoSessionConfig(year=None, question_count=50, shuffle=False)
    q_all = service.create_dojo_session(cfg_all)
    assert len(q_all) == 50
    # First 25 must be 2025, next 25 must be 2024
    assert all(q.year == 2025 for q in q_all[:25])
    assert all(q.year == 2024 for q in q_all[25:])

    # 4. Year + Category combination
    cfg_combo = DojoSessionConfig(
        mode=DojoMode.CATEGORY,
        year=2023,
        category="データベース設計",
        question_count=10,
        shuffle=False,
    )
    q_combo = service.create_dojo_session(cfg_combo)
    assert len(q_combo) >= 1
    assert all(q.year == 2023 for q in q_combo)
    assert all(q.category == "データベース設計" for q in q_combo)


def test_practice_attempt_records_correct_year_and_term(tmp_path):
    """Verify that answering a question from 2021 persists year=2021, term='秋期' into SQLite."""
    db_file = tmp_path / "test_history.db"
    history_repo = SQLitePracticeHistoryRepository(db_path=db_file)
    repo = LocalQuestionRepository()
    service = PracticeService(question_repo=repo, history_repo=history_repo)

    # Submit answer for 2021 Q01
    q_2021_01 = repo.get_question_by_id("2021-SA-AM2-Q01")
    assert q_2021_01 is not None

    res = service.submit_answer(
        question_id=q_2021_01.id,
        choice_key=AnswerKey("イ"),
        session_id="test-session-2021",
        time_spent_seconds=12.5,
    )

    assert res.is_correct is True

    # Check persistence
    attempts = history_repo.get_attempts()
    assert len(attempts) == 1
    saved = attempts[0]
    assert saved.question_id == "2021-SA-AM2-Q01"
    assert saved.year == 2021
    assert saved.term == "秋期"
    assert saved.question_number == 1
    assert saved.exam_type == "SA"
    assert saved.is_correct is True


def test_browse_three_axis_composite_filter():
    """Verify 3-axis composite search (year, category, keyword) logic used in question browsing."""
    repo = LocalQuestionRepository()
    all_questions = repo.get_all_questions()

    # Case 1: Filter by year 2022 and keyword "インセプションデッキ"
    target_year = 2022
    kw = "インセプションデッキ".lower()
    matches = [
        q
        for q in all_questions
        if q.year == target_year
        and (
            kw in q.question_text.lower()
            or kw in q.explanation.lower()
            or any(kw in c.text.lower() for c in q.choices)
            or any(kw in k.lower() for k in q.keywords)
        )
    ]
    assert len(matches) == 1
    assert matches[0].id == "2022-SA-AM2-Q01"
    assert matches[0].question_number == 1

    # Case 2: Filter by year 2025 and category "システムアーキテクチャ設計"
    matches_cat = [
        q for q in all_questions if q.year == 2025 and q.category == "システムアーキテクチャ設計"
    ]
    assert len(matches_cat) >= 1
    assert all(q.year == 2025 for q in matches_cat)

    # Case 3: Filter by non-existent year or keyword returns empty list safely
    matches_empty = [
        q
        for q in all_questions
        if q.year == 2021 and "存在しないキーワードXYZ123" in q.question_text
    ]
    assert matches_empty == []
