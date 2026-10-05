"""Test configuration and fixtures."""

import os

# Tests run as local development: auth is secure-by-default (True), so disable it
# explicitly BEFORE importing src (module-level `settings = Settings()`).
# Tests that verify auth construct Settings(auth_enabled=True, ...) explicitly.
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.pop("K_SERVICE", None)

import pytest  # noqa: E402

from src.domain.models import AnswerKey, ExamChoice, ExamQuestion  # noqa: E402


@pytest.fixture
def sample_question() -> ExamQuestion:
    return ExamQuestion(
        id="2025-SA-AM2-Q01",
        exam_type="SA",
        year=2025,
        term="春期",
        question_number=1,
        question_text="マイクロサービスアーキテクチャにおけるサーキットブレーカーパターンの説明として、適切なものはどれか。",
        choices=[
            ExamChoice(
                key=AnswerKey.A,
                text="クライアントからのリクエスト流量を制限し、バックエンドサービスの過負荷によるダウンを防止する。",
            ),
            ExamChoice(
                key=AnswerKey.I,
                text="外部サービスへの呼び出しの失敗が一定の閾値を超えた場合に即座に失敗を返し、障害の連鎖とリソース枯渇を防止する。",
            ),
            ExamChoice(
                key=AnswerKey.U,
                text="複数のサービスに跨るトランザクションを、補償トランザクションの連鎖によって結果整合性として完結させる。",
            ),
            ExamChoice(
                key=AnswerKey.E,
                text="サービスのデータ更新イベントを非同期メッセージとして発行し、複数のリードモデルへ複製・投影する。",
            ),
        ],
        correct_answer=AnswerKey.I,
        category="システムアーキテクチャ設計",
        explanation="サーキットブレーカーパターンはカスケード障害を防ぐための設計パターンです。",
        keywords=["サーキットブレーカー", "マイクロサービス"],
    )
