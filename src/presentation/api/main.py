"""FastAPI application entrypoint for IPA Exam RAG."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.application.rag_service import RAGService
from src.infrastructure.config import settings
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.presentation.api.deps import (
    get_llm_provider,
    get_question_repository,
    get_vector_store,
    require_authenticated_user,
)
from src.presentation.api.routers import analytics, auth, practice, questions, rag, system

logger = logging.getLogger(__name__)

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
FALLBACK_DIST_DIR = Path(__file__).resolve().parent.parent.parent.parent / "dist"


def resolve_static_dir(custom_path: Path | str | None = None) -> Path:
    """Resolve frontend static distribution directory."""
    if custom_path:
        return Path(custom_path).resolve()
    if DEFAULT_STATIC_DIR.exists():
        return DEFAULT_STATIC_DIR.resolve()
    if FALLBACK_DIST_DIR.exists():
        return FALLBACK_DIST_DIR.resolve()
    return DEFAULT_STATIC_DIR.resolve()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Execute startup and shutdown lifecycle hooks including SQLite schema migration and Qdrant seed check."""
    logger.info("Starting IPA Exam RAG API...")
    try:
        # Guarantee SQLite database initialization and pending schema migrations on startup
        repo = SQLitePracticeHistoryRepository()
        logger.info("Database schema migration check passed successfully: %s", repo.db_path)

        # Guarantee Qdrant vector store initialization and auto-seed if empty
        try:
            v_store = app.dependency_overrides.get(get_vector_store, get_vector_store)()
            llm_prov = app.dependency_overrides.get(get_llm_provider, get_llm_provider)()
            q_repo = app.dependency_overrides.get(
                get_question_repository, get_question_repository
            )()
            rag_service = RAGService(
                vector_store=v_store, llm_provider=llm_prov, question_repo=q_repo
            )
            seeded_count = rag_service.ensure_seeded()
            if seeded_count > 0:
                logger.info("Auto-seeded %d questions into Qdrant on startup.", seeded_count)
        except Exception as seed_err:
            logger.warning(
                "Qdrant auto-seed check skipped or encountered non-fatal error: %s", seed_err
            )
    except Exception as e:
        logger.error("Failed to run startup lifespan checks: %s", e)
        raise

    yield

    logger.info("Shutting down IPA Exam RAG API...")


def create_app(static_dir: Path | str | None = None) -> FastAPI:
    """Application factory configuring routes, middleware, and SPA fallback."""
    app = FastAPI(
        title="IPA Exam RAG API",
        description="FastAPI ASGI backend and SPA hosting for IPA Exam RAG system",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS for local development and production frontends
    # allow_methods: GET / POST / DELETE のみ（ルーター棚卸し済み）
    # allow_headers: Content-Type のみ（認証はクッキーで行うため Authorization 不要）
    # allow_credentials: True（セッションクッキー送受信に必要）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    # Health check endpoints
    @app.get("/health", tags=["system"], summary="Health check endpoint")
    @app.get("/api/health", tags=["system"], summary="API health check endpoint")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    # Include REST API routers
    # Enforce authentication guard on protected application routers when auth_enabled is True
    protected_dependencies = [Depends(require_authenticated_user)]
    app.include_router(questions.router, dependencies=protected_dependencies)
    app.include_router(practice.router, dependencies=protected_dependencies)
    app.include_router(analytics.router, dependencies=protected_dependencies)
    app.include_router(rag.router, dependencies=protected_dependencies)
    app.include_router(system.router, dependencies=protected_dependencies)
    # Auth endpoints must remain publicly accessible for login flow
    app.include_router(auth.router)

    # Mount static assets directory if it exists
    resolved_dir = resolve_static_dir(static_dir)
    assets_dir = resolved_dir / "assets"
    if assets_dir.exists() and assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # SPA HTML5 History API Fallback handler
    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa_fallback(full_path: str) -> Response:
        # Enforce API boundary: routes under /api/* must return 404 JSON, not SPA HTML
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API endpoint not found: /{full_path}",
            )

        # Serve static file directly if requested path exists in resolved_dir (e.g. favicon.ico, robots.txt)
        if full_path:
            requested_file = (resolved_dir / full_path).resolve()
            if requested_file.is_file() and requested_file.is_relative_to(resolved_dir):
                headers = {}
                if requested_file.name in ("sw.js", "manifest.webmanifest", "index.html"):
                    headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                return FileResponse(requested_file, headers=headers)

        # Serve SPA entrypoint index.html if built assets are available
        index_file = resolved_dir / "index.html"
        if index_file.exists() and index_file.is_file():
            return FileResponse(
                index_file,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )

        # Fallback placeholder HTML during development or headless testing
        return HTMLResponse(
            content=(
                "<!DOCTYPE html>"
                "<html lang='ja'>"
                "<head><meta charset='UTF-8'><title>IPA Exam RAG SPA</title></head>"
                "<body>"
                "<div id='root'><h1>IPA Exam RAG SPA</h1><p>Frontend SPA development mode fallback.</p></div>"
                "</body>"
                "</html>"
            ),
            status_code=status.HTTP_200_OK,
        )

    return app


app = create_app()
