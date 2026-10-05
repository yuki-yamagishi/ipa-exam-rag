"""System settings and maintenance management API router."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from src.application.rag_service import RAGService
from src.domain.interfaces import (
    ILLMProvider,
    IPracticeHistoryRepository,
    IVectorStore,
)
from src.infrastructure.config import Settings
from src.presentation.api.deps import (
    get_history_repository,
    get_llm_provider,
    get_rag_service,
    get_settings,
    get_vector_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


def mask_api_key(key: str | None) -> str:
    """Safely mask API key for display without raising exceptions on short or empty strings."""
    if not key:
        return ""
    stripped = key.strip()
    if not stripped:
        return ""
    if len(stripped) <= 8:
        if len(stripped) <= 4:
            return "****"
        return f"{stripped[:2]}...{stripped[-2:]}"
    return f"{stripped[:4]}...{stripped[-4:]}"


class SystemSettingsResponse(BaseModel):
    gemini_api_key_masked: str
    gemini_model_generate: str
    gemini_model_generate_fallback: str
    gemini_model_embedding: str
    vector_store_points_count: int
    auth_enabled: bool


class UpdateApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1, description="New Gemini API Key")

    @field_validator("api_key")
    @classmethod
    def validate_not_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("API key cannot be empty or whitespace only.")
        return stripped


class UpdateApiKeyResponse(BaseModel):
    success: bool
    gemini_api_key_masked: str
    message: str


class ReindexResponse(BaseModel):
    success: bool
    reindexed_count: int
    message: str


class ResetHistoryResponse(BaseModel):
    success: bool
    message: str


@router.get(
    "/settings",
    response_model=SystemSettingsResponse,
    summary="Get current system configuration and vector store stats",
)
def get_system_settings(
    settings: Annotated[Settings, Depends(get_settings)],
    vector_store: Annotated[IVectorStore, Depends(get_vector_store)],
) -> SystemSettingsResponse:
    """Return current system settings with masked API key and vector store point count."""
    try:
        points_count = vector_store.count()
    except Exception as e:
        logger.warning("Failed to retrieve vector store point count: %s", e)
        points_count = 0

    return SystemSettingsResponse(
        gemini_api_key_masked=mask_api_key(settings.gemini_api_key),
        gemini_model_generate=settings.gemini_model_generate,
        gemini_model_generate_fallback=settings.gemini_model_generate_fallback,
        gemini_model_embedding=settings.gemini_model_embedding,
        vector_store_points_count=points_count,
        auth_enabled=settings.auth_enabled,
    )


@router.post(
    "/api-key",
    response_model=UpdateApiKeyResponse,
    summary="Dynamically update Gemini API key",
)
def update_api_key(
    req: UpdateApiKeyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    llm_provider: Annotated[ILLMProvider, Depends(get_llm_provider)],
) -> UpdateApiKeyResponse:
    """Dynamically update Gemini API key for singleton LLM provider and settings."""
    try:
        llm_provider.update_api_key(req.api_key)
        settings.gemini_api_key = req.api_key
        logger.info("Gemini API key updated dynamically.")
        return UpdateApiKeyResponse(
            success=True,
            gemini_api_key_masked=mask_api_key(req.api_key),
            message="Gemini API キーを更新しました。",
        )
    except Exception as e:
        logger.error("Failed to update API key: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API キーの更新処理に失敗しました。",
        ) from e


@router.post(
    "/reindex",
    response_model=ReindexResponse,
    summary="Reindex all exam questions into vector store",
)
def reindex_all_questions(
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> ReindexResponse:
    """Reindex all exam questions from question repository into vector store."""
    try:
        count = rag_service.reindex_all()
        return ReindexResponse(
            success=True,
            reindexed_count=count,
            message=f"{count} 件の設問をベクトルストアに再インデックスしました。",
        )
    except Exception as e:
        logger.error("Reindexing failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="再インデックス処理に失敗しました。",
        ) from e


@router.post(
    "/reset-history",
    response_model=ResetHistoryResponse,
    summary="Reset all practice history and sessions",
)
def reset_practice_history(
    history_repo: Annotated[IPracticeHistoryRepository, Depends(get_history_repository)],
) -> ResetHistoryResponse:
    """Safely clear all practice attempts and dojo sessions."""
    try:
        history_repo.clear_all()
        logger.info("Practice history and sessions reset successfully.")
        return ResetHistoryResponse(
            success=True,
            message="すべての学習履歴および演習セッションを消去しました。",
        )
    except Exception as e:
        logger.error("Failed to reset practice history: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="学習履歴のリセット処理に失敗しました。",
        ) from e
