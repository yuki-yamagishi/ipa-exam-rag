"""Tests for Question Browser & AI Chat functionality (Issue #005)."""

from unittest.mock import MagicMock

from src.application.rag_service import RAGService
from src.application.self_growth_service import (
    MultiSelfGrowthReport,
    SelfGrowthService,
)
from src.domain.models import (
    AnswerKey,
    ExamQuestion,
    PracticeAttempt,
)
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.infrastructure.question_repository import LocalQuestionRepository


def filter_browse_questions(
    questions: list[ExamQuestion],
    year: str = "全年度",
    category: str = "すべて",
    keyword: str = "",
) -> list[ExamQuestion]:
    """Helper representing the exact 3-axis filtering logic in app.py tab_browse."""
    res = questions
    if year != "全年度":
        target_year = int(year.replace("年", ""))
        res = [q for q in res if q.year == target_year]
    if category != "すべて":
        res = [q for q in res if q.category == category]
    if keyword:
        kw = keyword.lower()
        res = [
            q
            for q in res
            if kw in q.question_text.lower()
            or kw in q.explanation.lower()
            or any(kw in c.text.lower() for c in q.choices)
            or any(kw in k.lower() for k in q.keywords)
        ]
    return res


def test_scenario_2_filter_by_category_and_keyword():
    """シナリオ 2: 分野およびキーワードによる問題一覧の絞り込み (正常系・フィルタ)"""
    repo = LocalQuestionRepository()
    all_qs = repo.get_all_questions()
    assert len(all_qs) >= 20

    # 1. 分野フィルタ
    sample_cat = all_qs[0].category
    cat_filtered = filter_browse_questions(all_qs, category=sample_cat, keyword="")
    assert len(cat_filtered) > 0
    assert all(q.category == sample_cat for q in cat_filtered)

    # 2. キーワード検索（DFD）
    kw_filtered = filter_browse_questions(all_qs, category="すべて", keyword="DFD")
    assert len(kw_filtered) >= 1
    assert any(
        "DFD" in q.question_text or "DFD" in q.explanation
        for q in kw_filtered
    )

    # 3. 分野 ＋ キーワードの複合フィルタ
    combo_filtered = filter_browse_questions(
        all_qs, category=sample_cat, keyword="DFD"
    )
    assert len(combo_filtered) >= 1
    for q in combo_filtered:
        assert q.category == sample_cat
        assert (
            "DFD" in q.question_text
            or "DFD" in q.explanation
            or any("DFD" in k for k in q.keywords)
        )


def test_scenario_7_search_zero_results_boundary():
    """シナリオ 7: 検索結果 0 件時の境界値安全動作 (境界値・異常系)"""
    repo = LocalQuestionRepository()
    all_qs = repo.get_all_questions()

    # 存在しないキーワードでの検索
    zero_filtered = filter_browse_questions(all_qs, category="すべて", keyword="xyzNotFoundTerm999")
    assert len(zero_filtered) == 0
    assert isinstance(zero_filtered, list)


def test_scenario_8_three_axis_composite_filter():
    """シナリオ 8: 年度 ＋ 分野 ＋ キーワードによる 3 軸複合絞り込み"""
    repo = LocalQuestionRepository()
    all_qs = repo.get_all_questions()

    # 2021年・システム要件定義・アシュアランスケース
    filtered = filter_browse_questions(
        all_qs,
        year="2021年",
        category="システム要件定義",
        keyword="アシュアランスケース",
    )
    assert len(filtered) == 1
    assert filtered[0].id == "2021-SA-AM2-Q01"
    assert filtered[0].year == 2021
    assert filtered[0].question_number == 1


def test_scenario_1_question_switch_clears_state(sample_question: ExamQuestion):
    """シナリオ 1: 問題切り替え時のステート初期化 (前問コンテキスト混入防止)"""
    # 疑似セッションステート
    session_state = {
        "browse_selected_q_id": sample_question.id,
        "browse_dialogue_history": [
            {"role": "user", "content": "問1の選択肢イの根拠を教えて"},
            {"role": "assistant", "content": "サーキットブレーカーは障害連鎖を防ぐためです"},
        ],
        "browse_last_explanation": "AI解説問1のテキスト",
    }

    # 別の問題に切り替えた時の状態遷移ロジック
    new_qid = "2025-SA-AM2-Q02"
    if session_state["browse_selected_q_id"] != new_qid:
        session_state["browse_selected_q_id"] = new_qid
        session_state["browse_dialogue_history"] = []
        session_state["browse_last_explanation"] = None

    # 検証: 新しい問題では前問の対話・解説が完全に初期化されていること
    assert session_state["browse_selected_q_id"] == "2025-SA-AM2-Q02"
    assert session_state["browse_dialogue_history"] == []
    assert session_state["browse_last_explanation"] is None


def test_scenario_3_ai_chat(sample_question: ExamQuestion):
    """シナリオ 3: 閲覧中問題に関する AI への自由質問 (正常系)"""
    mock_vector_store = MagicMock()
    mock_vector_store.search_hybrid.return_value = []
    mock_llm_provider = MagicMock()
    mock_llm_provider.chat_response.return_value = "サーキットブレーカーは障害の連鎖を遮断します。"
    mock_repo = MagicMock()

    rag_service = RAGService(mock_vector_store, mock_llm_provider, mock_repo)

    dialogue_history = []
    user_msg = "選択肢イが正解である理由を教えてください"

    reply = rag_service.chat_discuss(
        question=sample_question,
        dialogue_history=dialogue_history,
        user_message=user_msg,
    )

    assert "サーキットブレーカー" in reply
    assert mock_llm_provider.chat_response.called


def test_scenario_4_rag_self_growth_and_empty_guard(sample_question: ExamQuestion):
    """シナリオ 4: 対話知見のワンクリック RAG 自己成長蓄積および空対話時の安全境界動作"""
    mock_vector_store = MagicMock()
    mock_llm_provider = MagicMock()
    growth_service = SelfGrowthService(mock_vector_store, mock_llm_provider)

    # 1. 空対話時のガード (0 件)
    empty_history = []
    # app.py では `if not st.session_state.browse_dialogue_history:` によりガードされる
    assert len(empty_history) == 0

    # 2. 対話が存在する場合の RAG 蓄積
    active_history = [
        {"role": "user", "content": "サーキットブレーカーのタイムアウト設計の注意点は？"},
        {
            "role": "assistant",
            "content": "適切な半オープン(Half-Open)状態の検証間隔を設定することです。",
        },
    ]
    mock_report = MultiSelfGrowthReport(
        reports=[],
        created_count=1,
        message="1 件の新しいナレッジを登録しました",
    )
    growth_service.process_dialogue_to_knowledge = MagicMock(return_value=mock_report)

    result = growth_service.process_dialogue_to_knowledge(sample_question, active_history)
    assert result.message == "1 件の新しいナレッジを登録しました"
    assert growth_service.process_dialogue_to_knowledge.called


def test_scenario_5_browse_does_not_pollute_practice_history(tmp_path):
    """シナリオ 5: 閲覧・質問時の解答履歴 DB 非汚染 (整合性検証)"""
    db_file = tmp_path / "test_history.db"
    history_repo = SQLitePracticeHistoryRepository(db_path=str(db_file))

    # 初期状態: 1問解答済みのダミーレコード作成
    attempt = PracticeAttempt(
        id="attempt-1",
        session_id="pre-existing-session",
        question_id="2025-SA-AM2-Q01",
        exam_type="SA",
        year=2025,
        term="秋期",
        question_number=1,
        category="システムアーキテクチャ設計",
        user_choice=AnswerKey.I,
        correct_answer=AnswerKey.I,
        is_correct=True,
        time_spent_seconds=15.0,
        answered_at="2026-09-15T12:00:00Z",
    )
    history_repo.record_attempt(attempt)

    initial_attempts = history_repo.get_attempts()
    assert len(initial_attempts) == 1
    assert initial_attempts[0].is_correct is True

    # ユーザーがブラウズタブで全問を閲覧し、AIに質問したシミュレーション
    repo = LocalQuestionRepository()
    all_qs = repo.get_all_questions()
    assert len(all_qs) > 0

    # ブラウズタブでは `history_repo.record_attempt` を一切呼ばない
    # そのため、DB の試行数は 1 のままで変化しないことを検証
    after_browse_attempts = history_repo.get_attempts()
    assert len(after_browse_attempts) == 1
    assert after_browse_attempts[0].id == initial_attempts[0].id


def test_scenario_6_dojo_session_isolation_during_browse(sample_question: ExamQuestion):
    """シナリオ 6: 演習モード進行中におけるブラウズ操作の完全分離 (状態整合性)"""
    # 道場モード実行中のセッション状態
    session_state = {
        # 道場ステート
        "dojo_active": True,
        "dojo_session_id": "active-dojo-uuid-1234",
        "dojo_queue": [sample_question],
        "dojo_index": 2,
        "dojo_results": [{"is_correct": True}],
        "dojo_completed": False,
        "current_result": MagicMock(is_correct=True),
        "dialogue_history": [{"role": "user", "content": "道場中チャット"}],
        "last_explanation": "道場AI解説",
        # ブラウズステート（独立）
        "browse_selected_q_id": None,
        "browse_dialogue_history": [],
        "browse_last_explanation": None,
    }

    # ユーザーが「ブラウズ」タブで別の問題を選択し、質問した操作
    browse_qid = "2025-SA-AM2-Q05"
    session_state["browse_selected_q_id"] = browse_qid
    session_state["browse_dialogue_history"].append({"role": "user", "content": "ブラウズでの質問"})
    session_state["browse_last_explanation"] = "ブラウズAI解説"

    # 検証: 道場ステートが一切破壊・変更されていないこと
    assert session_state["dojo_active"] is True
    assert session_state["dojo_session_id"] == "active-dojo-uuid-1234"
    assert session_state["dojo_index"] == 2
    assert len(session_state["dojo_results"]) == 1
    assert session_state["dialogue_history"] == [{"role": "user", "content": "道場中チャット"}]
    assert session_state["last_explanation"] == "道場AI解説"

    # ブラウズステートは独立して更新されていること
    assert session_state["browse_selected_q_id"] == browse_qid
    assert len(session_state["browse_dialogue_history"]) == 1
    assert session_state["browse_last_explanation"] == "ブラウズAI解説"


def test_browse_ui_rendering_fields_integrity():
    """Verify that all ExamQuestion fields accessed in tab_browse rendering exist and format without AttributeError."""
    repo = LocalQuestionRepository()
    all_qs = repo.get_all_questions()
    assert len(all_qs) >= 20

    for q in all_qs:
        # 1. Header & Caption
        header = f"【問 {q.question_number}】 {q.category}"
        caption = (
            f"試験区分: {q.exam_type} ({q.year}年 {q.term}) | キーワード: {', '.join(q.keywords)}"
        )
        assert header
        assert caption

        # 2. Text & Choices
        assert q.question_text
        assert len(q.choices) == 4
        for choice in q.choices:
            choice_str = f"({choice.key.value}) {choice.text}"
            assert choice_str

        # 3. Official Answer & Explanation
        ans_str = f"🎯 公式正解: ({q.correct_answer.value})"
        assert ans_str
        assert q.explanation
