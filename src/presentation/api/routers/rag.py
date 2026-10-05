import json
import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.application.rag_service import RAGService
from src.application.self_growth_service import SelfGrowthService
from src.domain.interfaces import IQuestionRepository
from src.domain.models import AnswerKey, LearnedInsight, RetrievalChunk
from src.presentation.api.deps import (
    get_question_repository,
    get_rag_service,
    get_self_growth_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


class ExplainRequest(BaseModel):
    """Request payload for generating AI-grounded technical explanation."""

    question_id: str = Field(..., description="Target question ID to generate explanation for")
    user_choice: AnswerKey = Field(..., description="User's selected answer key (ア, イ, ウ, エ)")


class ExplainResponse(BaseModel):
    """Response payload containing generated technical explanation and grounding retrieval chunks."""

    question_id: str = Field(..., description="Question ID")
    explanation: str = Field(..., description="Grounded technical explanation text")
    context_chunks: list[RetrievalChunk] = Field(
        default_factory=list,
        description="Retrieved grounding knowledge chunks from official questions and learned insights",
    )


@router.post(
    "/explain",
    response_model=ExplainResponse,
    summary="Generate grounded AI technical explanation",
    description="Retrieve relevant past questions and insights from Qdrant, then generate technical explanation.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Question was not found",
            "content": {
                "application/json": {"example": {"detail": "Question not found: 2025-SA-AM2-Q99"}}
            },
        }
    },
)
def explain_question(
    req: ExplainRequest,
    service: Annotated[RAGService, Depends(get_rag_service)],
    question_repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
) -> ExplainResponse:
    question = question_repo.get_question_by_id(req.question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {req.question_id}",
        )

    explanation, chunks = service.explain_with_context(
        question=question,
        user_choice=req.user_choice,
    )
    return ExplainResponse(
        question_id=req.question_id,
        explanation=explanation,
        context_chunks=chunks,
    )


class ChatStreamRequest(BaseModel):
    """Request payload for SSE streaming dialogue chat."""

    question_id: str = Field(..., description="Target question ID")
    user_message: str = Field(..., min_length=1, description="User query or message")
    dialogue_history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Previous dialogue history e.g. [{'role': 'user', 'content': '...'}]",
    )


@router.post(
    "/chat/stream",
    summary="Interactive AI dialogue chat with SSE streaming",
    description="Stream conversational response tokens via Server-Sent Events with initial grounding citations.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Question was not found",
            "content": {
                "application/json": {"example": {"detail": "Question not found: 2025-SA-AM2-Q99"}}
            },
        },
        status.HTTP_200_OK: {
            "description": "Server-Sent Events stream",
            "content": {"text/event-stream": {}},
        },
    },
)
def chat_stream(
    req: ChatStreamRequest,
    service: Annotated[RAGService, Depends(get_rag_service)],
    question_repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
) -> StreamingResponse:
    question = question_repo.get_question_by_id(req.question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {req.question_id}",
        )

    def event_generator() -> Iterator[str]:
        try:
            chunks, stream_iter = service.chat_stream_with_context(
                question=question,
                dialogue_history=req.dialogue_history,
                user_message=req.user_message,
            )

            # 1. Send citation event first
            citations_data = [chunk.model_dump() for chunk in chunks]
            yield f"event: citation\ndata: {json.dumps(citations_data, ensure_ascii=False)}\n\n"

            # 2. Stream tokens
            for token in stream_iter:
                if token:
                    yield f"event: token\ndata: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            # 3. Send done event on successful completion
            yield f"event: done\ndata: {json.dumps({'status': 'completed'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("Error in SSE chat stream: %s", e)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class SaveKnowledgeRequest(BaseModel):
    """Request payload for extracting and indexing candidate insights in background."""

    question_id: str = Field(..., description="Target question ID")
    dialogue_history: list[dict[str, str]] = Field(
        ...,
        min_length=1,
        description="Dialogue message history e.g. [{'role': 'user', 'content': '...'}]",
    )


class SaveKnowledgeResponse(BaseModel):
    """Response payload acknowledging background knowledge extraction task."""

    status: str = Field(default="accepted", description="Task acceptance status")
    message: str = Field(
        default="Knowledge extraction and verification scheduled in background",
        description="User-facing status message",
    )
    question_id: str = Field(..., description="Target question ID")


@router.post(
    "/save-knowledge",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SaveKnowledgeResponse,
    summary="Schedule background knowledge extraction and verification",
    description="Asynchronously extract architectural insights from dialogue, verify with Judge Agent using Semaphore(2), and index into Qdrant.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Question was not found",
            "content": {
                "application/json": {"example": {"detail": "Question not found: 2025-SA-AM2-Q99"}}
            },
        },
        status.HTTP_202_ACCEPTED: {
            "description": "Task accepted and scheduled in background",
        },
    },
)
async def save_knowledge(
    req: SaveKnowledgeRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[SelfGrowthService, Depends(get_self_growth_service)],
    question_repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
) -> SaveKnowledgeResponse:
    question = question_repo.get_question_by_id(req.question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {req.question_id}",
        )

    async def _background_save_worker() -> None:
        try:
            logger.info(
                "Starting background knowledge extraction for question: %s", req.question_id
            )
            report = await service.process_dialogue_to_knowledge_async(
                question=question,
                dialogue_history=req.dialogue_history,
                max_concurrency=2,
            )
            logger.info(
                "Background knowledge extraction finished for %s: %s",
                req.question_id,
                report.message,
            )
        except Exception as e:
            logger.error(
                "Background knowledge extraction failed for %s: %s",
                req.question_id,
                e,
                exc_info=True,
            )

    background_tasks.add_task(_background_save_worker)

    return SaveKnowledgeResponse(
        status="accepted",
        message="Knowledge extraction and verification scheduled in background",
        question_id=req.question_id,
    )


@router.get(
    "/insights",
    response_model=list[LearnedInsight],
    summary="List learned insights",
    description="Retrieve all verified learned insights currently indexed in the vector store.",
)
def list_insights(
    service: Annotated[SelfGrowthService, Depends(get_self_growth_service)],
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum number of insights to retrieve")
    ] = 50,
) -> list[LearnedInsight]:
    return service.list_learned_insights(limit=limit)
