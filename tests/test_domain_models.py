"""Unit tests for domain models."""

import pytest
from pydantic import ValidationError

from src.domain.models import (
    AnswerKey,
    ExamChoice,
    ExamQuestion,
    KnowledgeCandidate,
    KnowledgeVerificationResult,
    LearnedInsight,
)


def test_exam_question_validation(sample_question: ExamQuestion):
    """Test valid ExamQuestion construction and methods."""
    assert sample_question.id == "2025-SA-AM2-Q01"
    assert sample_question.correct_answer == AnswerKey.I
    assert len(sample_question.choices) == 4

    choice_a = sample_question.get_choice(AnswerKey.A)
    assert choice_a is not None
    assert choice_a.key == AnswerKey.A

    full_text = sample_question.format_full_text()
    assert "【問題 1】" in full_text
    assert "(ア)" in full_text
    assert "(イ)" in full_text


def test_exam_question_choice_count_constraint():
    """Test that ExamQuestion requires exactly 4 choices."""
    with pytest.raises(ValidationError):
        ExamQuestion(
            id="INVALID",
            question_number=1,
            question_text="Invalid question with only 2 choices",
            choices=[
                ExamChoice(key=AnswerKey.A, text="Choice A"),
                ExamChoice(key=AnswerKey.I, text="Choice B"),
            ],
            correct_answer=AnswerKey.A,
            category="Test",
            explanation="Test",
        )


def test_knowledge_models_validation():
    """Test KnowledgeCandidate and LearnedInsight models."""
    candidate = KnowledgeCandidate(
        source_question_id="2025-SA-AM2-Q01",
        title="サーキットブレーカーのOpen状態移行条件",
        core_concept="連続失敗閾値を超えた場合に即時遮断する",
        trap_analysis="流量制限を行うレートリミッターと混同しやすい",
        practical_takeaway="リトライと組み合わせる際は指数バックオフを用いる",
        dialogue_context="ユーザーがレートリミッターとの違いを質問した",
        proposed_tags=["マイクロサービス", "サーキットブレーカー"],
    )
    assert candidate.source_question_id == "2025-SA-AM2-Q01"

    verification = KnowledgeVerificationResult(
        is_approved=True,
        confidence_score=0.92,
        critique="正確な記述でありIPAシラバスと完全一致する",
        refined_title="サーキットブレーカーとレートリミッターの相違",
        refined_core_concept="障害波及防止（CB）と過負荷防止（RL）の目的差",
        refined_trap_analysis="設問アはレートリミッターの説明である",
        tags=["マイクロサービス", "耐障害性"],
    )
    assert verification.is_approved is True
    assert verification.confidence_score == 0.92

    insight = LearnedInsight(
        id="insight-001",
        source_question_id="2025-SA-AM2-Q01",
        title=verification.refined_title,
        core_concept=verification.refined_core_concept,
        trap_analysis=verification.refined_trap_analysis,
        practical_takeaway=candidate.practical_takeaway,
        confidence_score=verification.confidence_score,
        tags=verification.tags,
    )
    doc_text = insight.format_document_text()
    assert "【学習知見】" in doc_text
    assert "障害波及防止" in doc_text
