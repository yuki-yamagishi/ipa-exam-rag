from functools import lru_cache
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from src.application.analytics_service import AnalyticsService
from src.application.practice_service import PracticeService
from src.application.rag_service import RAGService
from src.application.self_growth_service import SelfGrowthService
from src.domain.interfaces import (
    ILLMProvider,
    IPracticeHistoryRepository,
    IQuestionRepository,
    IVectorStore,
)
from src.infrastructure.auth_provider import GoogleAuthProvider
from src.infrastructure.config import Settings, settings
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.infrastructure.llm_provider import GoogleGenAIProvider
from src.infrastructure.qdrant_store import QdrantVectorStore
from src.infrastructure.question_repository import LocalQuestionRepository


@lru_cache
def get_settings() -> Settings:
    """Provide application settings singleton."""
    return settings


@lru_cache
def get_question_repository() -> IQuestionRepository:
    """Provide question repository singleton cached in-memory."""
    return LocalQuestionRepository()


def get_history_repository() -> IPracticeHistoryRepository:
    """Provide SQLite practice history repository instance."""
    return SQLitePracticeHistoryRepository()


@lru_cache
def get_vector_store() -> IVectorStore:
    """Provide Qdrant vector store instance."""
    return QdrantVectorStore()


@lru_cache
def get_llm_provider() -> ILLMProvider:
    """Provide Google GenAI LLM and embedding provider instance singleton."""
    return GoogleGenAIProvider()


@lru_cache
def get_auth_provider() -> GoogleAuthProvider:
    """Provide Google OAuth authentication provider singleton."""
    return GoogleAuthProvider()


def get_practice_service(
    question_repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
    history_repo: Annotated[IPracticeHistoryRepository, Depends(get_history_repository)],
) -> PracticeService:
    """Provide PracticeService instance with repository dependencies injected."""
    return PracticeService(question_repo=question_repo, history_repo=history_repo)


def get_analytics_service(
    history_repo: Annotated[IPracticeHistoryRepository, Depends(get_history_repository)],
    question_repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
) -> AnalyticsService:
    """Provide AnalyticsService instance with repository dependencies injected."""
    return AnalyticsService(history_repo=history_repo, question_repo=question_repo)


def get_rag_service(
    vector_store: Annotated[IVectorStore, Depends(get_vector_store)],
    llm_provider: Annotated[ILLMProvider, Depends(get_llm_provider)],
    question_repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
) -> RAGService:
    """Provide RAGService instance with vector store, LLM, and question repository injected."""
    return RAGService(
        vector_store=vector_store,
        llm_provider=llm_provider,
        question_repo=question_repo,
    )


def get_self_growth_service(
    vector_store: Annotated[IVectorStore, Depends(get_vector_store)],
    llm_provider: Annotated[ILLMProvider, Depends(get_llm_provider)],
) -> SelfGrowthService:
    """Provide SelfGrowthService instance with vector store and LLM provider injected."""
    return SelfGrowthService(
        vector_store=vector_store,
        llm_provider=llm_provider,
    )


def require_authenticated_user(
    settings: Annotated[Settings, Depends(get_settings)],
    auth_provider: Annotated[GoogleAuthProvider, Depends(get_auth_provider)],
    session_user: Annotated[str | None, Cookie()] = None,
) -> str | None:
    """Enforce authentication on protected API endpoints when auth_enabled is True.

    Returns user email if authenticated, or None if authentication is disabled.
    Raises HTTPException(401) if not logged in or session token is invalid/expired.
    Raises HTTPException(403) if user email is not in allowed_emails whitelist.
    """
    if not settings.auth_enabled:
        return None

    if not session_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です。Google アカウントでログインしてください。",
        )

    email = auth_provider.verify_session_token(session_user)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効または期限切れのセッションです。再度ログインしてください。",
        )

    if not auth_provider.is_email_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"メールアドレス '{email}' はアクセスが許可されていません。",
        )

    return email
