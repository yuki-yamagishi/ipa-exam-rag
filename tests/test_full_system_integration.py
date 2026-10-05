"""Full System Integration and End-to-End DoD Validation Test Suite (DoD-I1).

Verifies the integration of all 15 Definitions of Done (DoD-B1 ~ DoD-B7, DoD-F1 ~ DoD-F7, DoD-I1)
under the unified FastAPI ASGI application and Vite/React SPA architecture,
and confirms the complete deprecation of legacy Streamlit assets.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.domain.interfaces import ILLMProvider, IVectorStore
from src.domain.models import (
    AnswerKey,
    DocType,
    ExamQuestion,
    KnowledgeCandidate,
    KnowledgeVerificationResult,
    LearnedInsight,
    RetrievalChunk,
)
from src.infrastructure.auth_provider import GoogleAuthProvider
from src.infrastructure.config import Settings
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.infrastructure.question_repository import LocalQuestionRepository
from src.presentation.api.deps import (
    get_auth_provider,
    get_history_repository,
    get_llm_provider,
    get_question_repository,
    get_settings,
    get_vector_store,
)
from src.presentation.api.main import create_app


class MockLLMProvider(ILLMProvider):
    """Deterministic Mock LLM Provider for End-to-End System Testing."""

    def __init__(self) -> None:
        self.current_key = "AIzaSyMockKeyForFullIntegrationTest12345"

    def embed(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
        title: str | None = None,
        dimensionality: int = 768,
    ) -> list[float]:
        return [0.1] * dimensionality

    def embed_batch(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        dimensionality: int = 768,
    ) -> list[list[float]]:
        return [[0.1] * dimensionality for _ in texts]

    def generate_explanation(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        return f"公式根拠解説: 設問 {question.id} の正解は {question.correct_answer.value} です。"

    def chat_response(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        return f"回答: {user_message} に対する技術的な解説です。"

    def chat_stream(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> Generator[str, None, None]:
        yield "IPA試験の"
        yield "技術的ポイントを"
        yield "解説します。"

    def extract_knowledge_candidate(
        self, question: ExamQuestion, dialogue_history: list[dict[str, str]]
    ) -> KnowledgeCandidate | None:
        return KnowledgeCandidate(
            source_question_id=question.id,
            title="第3正規形の定義と推移的関数従属",
            core_concept="第3正規形は推移的関数従属を排除し、非キー属性が主キーにのみ依存する状態を指す。",
            trap_analysis="第2正規形（部分関数従属の排除）と混同しやすい。推移的従属と部分従属の違いを明確に区別すること。",
            practical_takeaway="DBスキーマ設計時は正規化レベルを意図的に選択し、過正規化によるJOINコスト増大とのトレードオフを評価する。",
            dialogue_context="ユーザーがデータベース正規化理論について質問した対話から抽出。",
            proposed_tags=["正規化", "データベース", "第3正規形"],
        )

    def extract_knowledge_candidates(
        self, question: ExamQuestion, dialogue_history: list[dict[str, str]]
    ) -> list[KnowledgeCandidate]:
        candidate = self.extract_knowledge_candidate(question, dialogue_history)
        return [candidate] if candidate else []

    def judge_knowledge(
        self, candidate: KnowledgeCandidate, question: ExamQuestion
    ) -> KnowledgeVerificationResult:
        return KnowledgeVerificationResult(
            is_approved=True,
            confidence_score=0.95,
            critique="妥当な技術的洞察です。",
            refined_title="第3正規形の定義と推移的関数従属",
            refined_core_concept="推移的関数従属を排除してテーブルを分割する。",
            refined_trap_analysis="第2正規形との混同に注意。",
            tags=["正規化", "データベース"],
        )

    def update_api_key(self, api_key: str) -> None:
        self.current_key = api_key


class MockVectorStore(IVectorStore):
    """In-memory Vector Store for End-to-End System Testing."""

    def __init__(self) -> None:
        self.sample_chunks = [
            RetrievalChunk(
                id="doc_mock_1",
                content="関係データベースの正規化理論に関する公式解説ドキュメント",
                score=0.92,
                doc_type=DocType.EXAM_QUESTION,
                metadata={"title": "DB正規化", "year": 2025},
            )
        ]

    def setup_collection(self, collection_name: str | None = None) -> None:
        pass

    def upsert_exam_questions(
        self, questions: list[ExamQuestion], embeddings: list[list[float]]
    ) -> None:
        pass

    def upsert_insight(self, insight: LearnedInsight, embedding: list[float]) -> None:
        pass

    def search_hybrid(
        self,
        query_text: str,
        query_dense_vector: list[float],
        limit: int = 5,
        filter_doc_types: list[DocType] | None = None,
    ) -> list[RetrievalChunk]:
        return self.sample_chunks[:limit]

    def find_most_similar_insight(
        self, query_dense_vector: list[float], threshold: float = 0.88
    ) -> tuple[LearnedInsight | None, float]:
        return None, 0.0

    def list_insights(self, limit: int = 50) -> list[LearnedInsight]:
        return []

    def count(self) -> int:
        return 125


@pytest.fixture
def integration_client(tmp_path: Path):
    """Provide fully configured TestClient with isolated SQLite database and mock dependencies."""
    test_db = tmp_path / "test_full_system.db"
    test_history_repo = SQLitePracticeHistoryRepository(db_path=test_db)
    test_q_repo = LocalQuestionRepository()
    test_llm = MockLLMProvider()
    test_vector_store = MockVectorStore()
    test_auth_provider = GoogleAuthProvider(allowed_emails=["test@example.com"])

    test_settings = Settings(
        gemini_api_key="AIzaSyMockKeyForFullIntegrationTest12345",
        gemini_model_generate="gemini-2.5-flash",
        gemini_model_generate_fallback="gemini-1.5-flash",
        auth_enabled=True,
        allowed_emails=["test@example.com"],
        cookie_secure=False,
        session_secret="test-session-secret-for-full-integration-testing",
    )

    app = create_app()

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_history_repository] = lambda: test_history_repo
    app.dependency_overrides[get_question_repository] = lambda: test_q_repo
    app.dependency_overrides[get_llm_provider] = lambda: test_llm
    app.dependency_overrides[get_vector_store] = lambda: test_vector_store
    app.dependency_overrides[get_auth_provider] = lambda: test_auth_provider

    with TestClient(app) as client:
        valid_token = test_auth_provider.generate_session_token("test@example.com")
        client.cookies.set("session_user", valid_token)
        yield client

    app.dependency_overrides.clear()


# =========================================================================
# Scenario 1: Multi-stage Dockerfile and ASGI Server Specification (DoD-I1)
# =========================================================================
def test_scenario_1_dockerfile_specification():
    """Verify Dockerfile contains multi-stage stages, correct Uvicorn entrypoint, and /health check."""
    root_dir = Path(__file__).resolve().parent.parent
    dockerfile_path = root_dir / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist at project root"

    content = dockerfile_path.read_text(encoding="utf-8")

    # Multi-stage targets
    assert "FROM node:20-slim AS frontend-builder" in content, (
        "Stage 1 must build frontend assets using Node.js"
    )
    assert "FROM python:3.12-slim AS backend-builder" in content, (
        "Stage 2 must build Python dependencies"
    )
    assert "FROM python:3.12-slim AS runner" in content, "Stage 3 must be minimal production runner"

    # Asset transfer and Entrypoint
    assert "COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist" in content, (
        "Runner stage must bundle built frontend dist"
    )
    assert 'ENTRYPOINT ["uvicorn", "src.presentation.api.main:create_app"' in content, (
        "Entrypoint must execute FastAPI ASGI app via Uvicorn factory"
    )
    assert "--port" in content and "8080" in content, "Must expose and run on PORT 8080"
    assert "/health" in content, "Healthcheck must probe /health endpoint"


# =========================================================================
# Scenario 2: Complete Deprecation of Legacy Streamlit Assets (DoD-I1)
# =========================================================================
def test_scenario_2_complete_deprecation_of_streamlit():
    """Verify src/presentation/app.py is deleted and streamlit is absent from pyproject.toml."""
    root_dir = Path(__file__).resolve().parent.parent
    app_py_path = root_dir / "src" / "presentation" / "app.py"
    assert not app_py_path.exists(), "src/presentation/app.py must be completely deleted"

    pyproject_path = root_dir / "pyproject.toml"
    pyproject_content = pyproject_path.read_text(encoding="utf-8")
    assert "streamlit" not in pyproject_content, (
        "pyproject.toml dependencies must not contain streamlit"
    )


# =========================================================================
# Scenario 3: SPA HTML5 History API Fallback & Asset Serving (DoD-F1 ~ F7)
# =========================================================================
def test_scenario_3_spa_fallback_and_boundary(integration_client: TestClient):
    """Verify SPA client routes return 200 HTML, while undefined /api/* routes return 404 JSON."""
    client = integration_client

    # 1. Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "healthy"}

    # 2. SPA client routes return HTML (200 OK)
    spa_routes = ["/", "/practice", "/questions", "/chat", "/insights", "/analytics"]
    for route in spa_routes:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} should return 200"
        assert "text/html" in res.headers["content-type"], f"Route {route} should return HTML"

    # 3. API boundary protection: non-existent /api/* returns 404 JSON, not SPA HTML
    res_api_404 = client.get("/api/non-existent-endpoint")
    assert res_api_404.status_code == 404
    assert res_api_404.headers["content-type"].startswith("application/json")
    assert "API endpoint not found" in res_api_404.json()["detail"]


# =========================================================================
# Scenario 4: Full 15-DoD End-to-End Lifecycle Integration (DoD-B1 ~ B7)
# =========================================================================
def test_scenario_4_full_15_dod_lifecycle_integration(integration_client: TestClient):
    """End-to-End integration test traversing questions catalog, dojo practice, analytics, RAG, and settings."""
    client = integration_client

    # --- [DoD-B1: Question Catalog] ---
    res_catalog = client.get("/api/questions?limit=5")
    assert res_catalog.status_code == 200
    catalog = res_catalog.json()
    assert catalog["total"] > 0
    first_q = catalog["items"][0]
    question_id = first_q["id"]

    # --- [DoD-B2: Practice Dojo Session & Submission] ---
    # Create dojo session
    res_session = client.post(
        "/api/practice/sessions",
        json={
            "mode": "all",
            "selected_years": [2025],
            "selected_categories": ["テクノロジ系"],
            "total_questions": 1,
        },
    )
    assert res_session.status_code == 201
    session_data = res_session.json()
    assert session_data["session"]["is_completed"] is False

    # Submit practice answer
    res_submit = client.post(
        "/api/practice/submit",
        json={
            "question_id": question_id,
            "choice_key": "ア",
            "time_spent_seconds": 15,
        },
    )
    assert res_submit.status_code == 200
    submit_data = res_submit.json()
    assert "is_correct" in submit_data
    assert submit_data["user_choice"] == "ア"

    # Check resumable session active status
    res_active = client.get("/api/practice/sessions/active")
    assert res_active.status_code == 200

    # --- [DoD-B3: Analytics Dashboard Summary] ---
    res_analytics = client.get("/api/analytics/summary")
    assert res_analytics.status_code == 200
    analytics_data = res_analytics.json()
    assert analytics_data["total_attempts"] >= 1

    # --- [DoD-B4: RAG Explanation Generation] ---
    res_explain = client.post(
        "/api/rag/explain",
        json={"question_id": question_id, "user_choice": "ア"},
    )
    assert res_explain.status_code == 200
    explain_data = res_explain.json()
    assert "explanation" in explain_data
    assert len(explain_data["context_chunks"]) > 0

    # --- [DoD-B5: SSE Streaming Dialogue with Citation] ---
    res_stream = client.post(
        "/api/rag/chat/stream",
        json={
            "question_id": question_id,
            "user_message": "正規化理論について教えてください",
            "dialogue_history": [],
        },
    )
    assert res_stream.status_code == 200
    assert "text/event-stream" in res_stream.headers["content-type"]
    stream_text = res_stream.text
    assert "event: citation" in stream_text
    assert "event: token" in stream_text
    assert "event: done" in stream_text

    # --- [DoD-B6: Knowledge Self-Growth & BackgroundTasks] ---
    res_save = client.post(
        "/api/rag/save-knowledge",
        json={
            "question_id": question_id,
            "dialogue_history": [
                {"role": "user", "content": "正規化について理解しました"},
                {"role": "assistant", "content": "第3正規形は推移的関数従属を排除します。"},
            ],
        },
    )
    assert res_save.status_code == 202
    assert res_save.json()["status"] == "accepted"

    # Fetch learned insights list
    res_insights = client.get("/api/rag/insights")
    assert res_insights.status_code == 200
    assert isinstance(res_insights.json(), list)

    # --- [DoD-B7: System Settings & Dynamic API Key Update] ---
    res_settings = client.get("/api/system/settings")
    assert res_settings.status_code == 200
    settings_data = res_settings.json()
    assert "AIza" in settings_data["gemini_api_key_masked"]
    assert settings_data["vector_store_points_count"] == 125

    # Dynamically update API key
    new_key = "AIzaSyNewUpdatedKey9876543210"
    res_update_key = client.post(
        "/api/system/api-key",
        json={"api_key": new_key},
    )
    assert res_update_key.status_code == 200
    assert res_update_key.json()["success"] is True

    # Check auth status
    res_auth = client.get("/api/auth/status")
    assert res_auth.status_code == 200

    # Get login URL
    res_login = client.get("/api/auth/login")
    assert res_login.status_code == 200
    assert "login_url" in res_login.json()


# =========================================================================
# Scenario 5: Cloud Run Deployment Specification Verification (DoD-I1)
# =========================================================================
def test_scenario_5_cloud_run_deployment_doc():
    """Verify docs/cloud_run_deployment.md exists and specifies --no-cpu-throttling and environment configs."""
    root_dir = Path(__file__).resolve().parent.parent
    deploy_doc = root_dir / "docs" / "cloud_run_deployment.md"
    assert deploy_doc.exists(), "docs/cloud_run_deployment.md must exist"

    doc_content = deploy_doc.read_text(encoding="utf-8")
    assert "--no-cpu-throttling" in doc_content, (
        "Deployment guide must mandate --no-cpu-throttling to prevent freezing background tasks"
    )
    assert "8080" in doc_content, "Deployment guide must document port 8080"
    assert "GEMINI_API_KEY" in doc_content, "Deployment guide must document GEMINI_API_KEY"
