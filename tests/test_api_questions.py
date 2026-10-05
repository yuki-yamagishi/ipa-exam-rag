"""Tests for FastAPI foundation and question catalog API (Issue #012 / DoD-B1)."""

import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.domain.models import AnswerKey, ExamChoice, ExamQuestion
from src.infrastructure.migrations.migrator import SchemaMigrator
from src.presentation.api.deps import get_question_repository
from src.presentation.api.main import create_app
from src.presentation.api.routers.questions import filter_questions


@pytest.fixture
def mock_questions() -> list[ExamQuestion]:
    """Sample mock questions for deterministic testing."""
    return [
        ExamQuestion(
            id="2025-SA-AM2-Q01",
            year=2025,
            term="春期",
            exam_type="SA",
            question_number=1,
            category="テクノロジ系",
            question_text="マイクロサービスにおいてサーキットブレーカーパターンの目的はどれか。",
            choices=[
                ExamChoice(key=AnswerKey.A, text="障害の連鎖を防止しシステムの回復性を高める"),
                ExamChoice(key=AnswerKey.I, text="データベースの正規化を行う"),
                ExamChoice(key=AnswerKey.U, text="通信を暗号化する"),
                ExamChoice(key=AnswerKey.E, text="キャッシュを削除する"),
            ],
            correct_answer=AnswerKey.A,
            explanation="サーキットブレーカーは障害の連鎖（Cascading Failure）を防ぐ設計パターンです。",
            keywords=["マイクロサービス", "サーキットブレーカー", "回復性"],
        ),
        ExamQuestion(
            id="2024-SA-AM2-Q05",
            year=2024,
            term="春期",
            exam_type="SA",
            question_number=5,
            category="マネジメント系",
            question_text="アジャイル開発におけるスプリントレトロスペクティブの目的はどれか。",
            choices=[
                ExamChoice(
                    key=AnswerKey.A, text="プロセスやチームの改善点を洗い出し次のスプリントに活かす"
                ),
                ExamChoice(key=AnswerKey.I, text="進捗を顧客に報告する"),
                ExamChoice(key=AnswerKey.U, text="成果物のリリース判定を行う"),
                ExamChoice(key=AnswerKey.E, text="開発予算を再計算する"),
            ],
            correct_answer=AnswerKey.A,
            explanation="レトロスペクティブは振り返りを通じてチームのプロセス改善を行うイベントです。",
            keywords=["アジャイル", "スクラム", "レトロスペクティブ"],
        ),
        ExamQuestion(
            id="2023-SA-AM2-Q10",
            year=2023,
            term="春期",
            exam_type="SA",
            question_number=10,
            category="ストラテジ系",
            question_text="DX（デジタルトランスフォーメーション）の定義として適切なものはどれか。",
            choices=[
                ExamChoice(
                    key=AnswerKey.A, text="データとデジタル技術を活用してビジネスモデルを変革する"
                ),
                ExamChoice(key=AnswerKey.I, text="紙の書類をPDF化する"),
                ExamChoice(key=AnswerKey.U, text="パソコンを最新型に買い替える"),
                ExamChoice(key=AnswerKey.E, text="社内LANの速度を向上させる"),
            ],
            correct_answer=AnswerKey.A,
            explanation="DXは単なるIT化ではなくビジネス変革を指します。",
            keywords=["DX", "ビジネスモデル", "変革"],
        ),
    ]


class MockQuestionRepository:
    """Mock repository with controllable dataset."""

    def __init__(self, questions: list[ExamQuestion]):
        self.questions = questions

    def get_all_questions(self) -> list[ExamQuestion]:
        return list(self.questions)

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

    def get_available_years(self) -> list[int]:
        return sorted({q.year for q in self.questions}, reverse=True)

    def get_questions_by_year(self, year: int) -> list[ExamQuestion]:
        return [q for q in self.questions if q.year == year]


@pytest.fixture
def client_with_mock_repo(mock_questions: list[ExamQuestion]) -> Generator[TestClient, None, None]:
    """TestClient with dependency overrides and lifespan support."""
    app = create_app()
    mock_repo = MockQuestionRepository(mock_questions)
    app.dependency_overrides[get_question_repository] = lambda: mock_repo

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def live_client() -> Generator[TestClient, None, None]:
    """TestClient using live 125 seed questions and real lifespan."""
    app = create_app()
    with TestClient(app) as client:
        yield client


# --- Acceptance Scenario 1: Lifespan & Health Check ---
def test_scenario_1_lifespan_and_health_check(live_client: TestClient, tmp_path: Path):
    """シナリオ 1: FastAPI アプリケーション起動時の Lifespan 実行とヘルスチェック"""
    # Verify health endpoints
    res1 = live_client.get("/health")
    assert res1.status_code == 200
    assert res1.json() == {"status": "healthy"}

    res2 = live_client.get("/api/health")
    assert res2.status_code == 200
    assert res2.json() == {"status": "healthy"}

    # Verify SQLite schema migration works in isolation via SchemaMigrator
    db_file = tmp_path / "test_migration.db"
    conn = sqlite3.connect(db_file)
    try:
        migrator = SchemaMigrator()
        applied = migrator.apply_all(conn)
        assert applied >= 3  # At least V1, V2, V3 migrations applied
        assert SchemaMigrator.get_current_version(conn) >= 3
    finally:
        conn.close()


# --- Acceptance Scenario 2: Questions List & Pagination ---
def test_scenario_2_list_questions_pagination(live_client: TestClient):
    """シナリオ 2: 過去問一覧の全件取得およびページネーション"""
    res = live_client.get("/api/questions?limit=10&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 125
    assert len(data["items"]) == 10
    assert data["limit"] == 10
    assert data["offset"] == 0

    # Test second page offset
    res_page2 = live_client.get("/api/questions?limit=10&offset=10")
    assert res_page2.status_code == 200
    data_page2 = res_page2.json()
    assert data_page2["total"] == 125
    assert len(data_page2["items"]) == 10
    assert data_page2["offset"] == 10
    assert data_page2["items"][0]["id"] != data["items"][0]["id"]


# --- Acceptance Scenario 3: 3-Axis Search Filtering ---
def test_scenario_3_search_filtering(live_client: TestClient):
    """シナリオ 3: 年度・分野・キーワードによる 3 軸複合検索"""
    # 1. Year filter
    res_year = live_client.get("/api/questions?year=2025")
    assert res_year.status_code == 200
    year_data = res_year.json()
    assert year_data["total"] == 25
    assert all(q["year"] == 2025 for q in year_data["items"])

    # 2. Category filter
    res_cat = live_client.get("/api/questions?category=システムアーキテクチャ設計")
    assert res_cat.status_code == 200
    cat_data = res_cat.json()
    assert cat_data["total"] > 0
    assert all(q["category"] == "システムアーキテクチャ設計" for q in cat_data["items"])

    # 3. Keyword filter
    res_kw = live_client.get("/api/questions?keyword=DFD")
    assert res_kw.status_code == 200
    kw_data = res_kw.json()
    assert kw_data["total"] >= 1
    assert any("DFD" in q["question_text"] for q in kw_data["items"])

    # 4. Combined 3-axis filter
    res_combined = live_client.get(
        "/api/questions?year=2025&category=システム要件定義&keyword=DFD"
    )
    assert res_combined.status_code == 200
    combined_data = res_combined.json()
    assert combined_data["total"] >= 1
    assert all(
        q["year"] == 2025 and q["category"] == "システム要件定義"
        for q in combined_data["items"]
    )


# --- Acceptance Scenario 4: Available Years and Categories ---
def test_scenario_4_get_years_and_categories(live_client: TestClient):
    """シナリオ 4: 利用可能な年度一覧および分野一覧の取得"""
    res_years = live_client.get("/api/questions/years")
    assert res_years.status_code == 200
    years = res_years.json()
    assert isinstance(years, list)
    assert len(years) == 5
    assert years == [2025, 2024, 2023, 2022, 2021]

    res_cats = live_client.get("/api/questions/categories")
    assert res_cats.status_code == 200
    categories = res_cats.json()
    assert isinstance(categories, list)
    assert "システムアーキテクチャ設計" in categories
    assert len(categories) > 0


# --- Acceptance Scenario 5: Question Detail Success ---
def test_scenario_5_get_question_detail_success(live_client: TestClient):
    """シナリオ 5: 単一設問詳細の取得（正常系）"""
    res = live_client.get("/api/questions/2025-SA-AM2-Q01")
    assert res.status_code == 200
    q = res.json()
    assert q["id"] == "2025-SA-AM2-Q01"
    assert q["year"] == 2025
    assert q["question_number"] == 1
    assert "DFD" in q["question_text"]
    assert len(q["choices"]) == 4
    assert q["correct_answer"] == "エ"
    assert "explanation" in q
    assert len(q["keywords"]) > 0


# --- Acceptance Scenario 6: Question Detail 404 Not Found ---
def test_scenario_6_get_question_detail_not_found(live_client: TestClient):
    """シナリオ 6: 存在しない設問ID指定時の 404 エラー返却（異常系）"""
    res = live_client.get("/api/questions/INVALID-ID-999")
    assert res.status_code == 404
    err = res.json()
    assert "detail" in err
    assert "Question not found: INVALID-ID-999" in err["detail"]


# --- Acceptance Scenario 7: SPA HTML5 History API Fallback ---
def test_scenario_7_spa_history_fallback_placeholder(live_client: TestClient):
    """シナリオ 7: 未定義パスに対する SPA HTML5 History API Fallback（プレースホルダー）"""
    for route in ["/", "/dojo", "/browse/2025-SA-AM2-Q01", "/analytics", "/settings"]:
        res = live_client.get(route)
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert ("<div id='root'>" in res.text) or ('<div id="root">' in res.text)


def test_scenario_7_spa_history_fallback_with_real_index_file():
    """シナリオ 7: dist/index.html が存在する場合の実ファイル配信 Fallback"""
    with tempfile.TemporaryDirectory() as tmp_dist:
        dist_dir = Path(tmp_dist)
        index_html = dist_dir / "index.html"
        index_html.write_text(
            "<!DOCTYPE html><html><body><div id='root'>Mock Real SPA</div></body></html>",
            encoding="utf-8",
        )

        app = create_app(static_dir=dist_dir)
        with TestClient(app) as client:
            res = client.get("/practice/sessions")
            assert res.status_code == 200
            assert "text/html" in res.headers["content-type"]
            assert "Mock Real SPA" in res.text


def test_scenario_7_root_static_file_direct_serving():
    """シナリオ 7: ルート直下静的ファイル (favicon.ico, manifest.webmanifest) の直接配信"""
    with tempfile.TemporaryDirectory() as tmp_dist:
        dist_dir = Path(tmp_dist)
        index_html = dist_dir / "index.html"
        index_html.write_text("<!DOCTYPE html><html><body>SPA</body></html>", encoding="utf-8")

        favicon = dist_dir / "favicon.ico"
        favicon.write_bytes(b"\x00\x00\x01\x00fake-ico-data")

        manifest = dist_dir / "manifest.webmanifest"
        manifest.write_text('{"name": "IPA Exam RAG"}', encoding="utf-8")

        app = create_app(static_dir=dist_dir)
        with TestClient(app) as client:
            # 1. Favicon should return direct file, not index.html
            res_fav = client.get("/favicon.ico")
            assert res_fav.status_code == 200
            assert res_fav.content == b"\x00\x00\x01\x00fake-ico-data"

            # 2. Manifest should return direct JSON file
            res_man = client.get("/manifest.webmanifest")
            assert res_man.status_code == 200
            assert '{"name": "IPA Exam RAG"}' in res_man.text

            # 3. Non-existent static-like route falls back to index.html
            res_fallback = client.get("/non-existent-page")
            assert res_fallback.status_code == 200
            assert "SPA" in res_fallback.text


def test_cors_headers(live_client: TestClient):
    """CORS 設定のテスト: 許可されたオリジンに対する適切なヘッダー返却"""
    headers = {"Origin": "http://localhost:5173"}
    res = live_client.get("/api/questions/years", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert res.headers.get("access-control-allow-credentials") == "true"


# --- Acceptance Scenario 8: API Boundary 404 JSON Protection ---
def test_scenario_8_api_boundary_protection(live_client: TestClient):
    """シナリオ 8: 存在しない /api/* パスに対する 404 JSON 返却（API 境界保護）"""
    res = live_client.get("/api/non-existent-endpoint")
    assert res.status_code == 404
    assert res.headers["content-type"] == "application/json"
    data = res.json()
    assert "detail" in data
    assert "API endpoint not found: /api/non-existent-endpoint" in data["detail"]

    # Root /api also returns 404 JSON
    res_api_root = live_client.get("/api")
    assert res_api_root.status_code == 404
    assert res_api_root.headers["content-type"] == "application/json"


# --- Unit Tests for filter_questions helper ---
def test_filter_questions_unit(mock_questions: list[ExamQuestion]):
    """Unit test for filtering logic helper."""
    # Empty filter returns all
    assert len(filter_questions(mock_questions)) == 3

    # Year filter
    assert len(filter_questions(mock_questions, year=2024)) == 1
    assert filter_questions(mock_questions, year=2024)[0].id == "2024-SA-AM2-Q05"

    # Category filter
    assert len(filter_questions(mock_questions, category="ストラテジ系")) == 1

    # Keyword in choices
    assert len(filter_questions(mock_questions, keyword="PDF化")) == 1

    # Keyword in explanation
    assert len(filter_questions(mock_questions, keyword="振り返り")) == 1

    # Keyword in tags
    assert len(filter_questions(mock_questions, keyword="回復性")) == 1

    # Non-matching keyword
    assert len(filter_questions(mock_questions, keyword="存在しないキーワードXYZ")) == 0


def test_dependency_override_with_mock_repo(client_with_mock_repo: TestClient):
    """Test API behavior when question repository is overridden with mock."""
    res = client_with_mock_repo.get("/api/questions")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # Years
    res_years = client_with_mock_repo.get("/api/questions/years")
    assert res_years.status_code == 200
    assert res_years.json() == [2025, 2024, 2023]

    # Detail
    res_q = client_with_mock_repo.get("/api/questions/2025-SA-AM2-Q01")
    assert res_q.status_code == 200
    assert res_q.json()["id"] == "2025-SA-AM2-Q01"
