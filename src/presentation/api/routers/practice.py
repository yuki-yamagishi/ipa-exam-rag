"""Practice session and answer submission API router."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.application.practice_service import PracticeResult, PracticeService
from src.domain.models import (
    AnswerKey,
    DojoSessionConfig,
    DojoSessionState,
    ExamQuestion,
)
from src.presentation.api.deps import (
    get_practice_service,
    require_authenticated_user,
)

router = APIRouter(prefix="/api/practice", tags=["practice"])


class SubmitAnswerRequest(BaseModel):
    """Request payload for submitting an answer to an exam question."""

    question_id: str = Field(..., description="ID of the question being answered")
    choice_key: AnswerKey = Field(..., description="Selected choice key (ア, イ, ウ, エ)")
    session_id: str | None = Field(default=None, description="Active session ID if in dojo mode")
    time_spent_seconds: float = Field(default=0.0, ge=0.0, description="Time spent in seconds")


class DojoSessionResponse(BaseModel):
    """Response returned upon successful creation of a dojo practice session."""

    session: DojoSessionState = Field(..., description="Active session metadata and progress")
    questions: list[ExamQuestion] = Field(
        ..., description="Ordered question queue for this session"
    )


class ActiveSessionResponse(BaseModel):
    """Response returned when querying for an active resumable dojo session."""

    session: DojoSessionState | None = Field(
        default=None, description="Active session if one exists, null otherwise"
    )
    questions: list[ExamQuestion] = Field(
        default_factory=list, description="Ordered question queue for the active session"
    )


class UpdateProgressRequest(BaseModel):
    """Request payload for saving ongoing session progress."""

    current_index: int = Field(ge=0, description="Current question index in queue")
    results: list[dict[str, Any]] = Field(
        default_factory=list, description="List of recorded attempt result dicts"
    )


class StatusResponse(BaseModel):
    """Generic status acknowledgement response."""

    status: str = Field(..., description="Operation status description")


def _verify_session_ownership(
    session: DojoSessionState, current_user: str | None
) -> None:
    """Ensure that the caller owns this session when authentication is active."""
    if current_user and session.user_email and session.user_email != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この演習セッションを操作する権限がありません。",
        )


@router.post(
    "/submit",
    response_model=PracticeResult,
    summary="Submit question answer",
    description="Evaluate user answer, record attempt in database, and return scoring result.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Question ID was not found",
            "content": {
                "application/json": {"example": {"detail": "Question not found: INVALID-Q999"}}
            },
        }
    },
)
def submit_answer(
    req: SubmitAnswerRequest,
    service: Annotated[PracticeService, Depends(get_practice_service)],
    current_user: Annotated[str | None, Depends(require_authenticated_user)] = None,
) -> PracticeResult:
    try:
        return service.submit_answer(
            question_id=req.question_id,
            choice_key=req.choice_key,
            session_id=req.session_id,
            time_spent_seconds=req.time_spent_seconds,
            user_email=current_user or "",
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {req.question_id}",
        ) from err


@router.post(
    "/sessions",
    response_model=DojoSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create dojo practice session",
    description="Build an ordered question queue according to configuration and initialize session.",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "No questions matched the specified criteria",
            "content": {
                "application/json": {
                    "example": {"detail": "No questions match the specified session criteria"}
                }
            },
        }
    },
)
def create_session(
    config: DojoSessionConfig,
    service: Annotated[PracticeService, Depends(get_practice_service)],
    current_user: Annotated[str | None, Depends(require_authenticated_user)] = None,
) -> DojoSessionResponse:
    effective_email = current_user if current_user else config.user_email
    queue = service.create_dojo_session(config)
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No questions match the specified session criteria",
        )

    session_id = str(uuid.uuid4())
    session_state = DojoSessionState(
        session_id=session_id,
        user_email=effective_email,
        mode=config.mode,
        year=config.year,
        category=config.category,
        question_count=len(queue),
        shuffle=config.shuffle,
        question_ids=[q.id for q in queue],
        current_index=0,
        results=[],
        is_completed=False,
    )
    service.save_session_progress(session_state)

    return DojoSessionResponse(session=session_state, questions=queue)


@router.get(
    "/sessions/active",
    response_model=ActiveSessionResponse,
    summary="Get active resumable session",
    description="Fetch the most recent uncompleted dojo session and its question queue.",
)
def get_active_session(
    service: Annotated[PracticeService, Depends(get_practice_service)],
    user_email: Annotated[str, Query(description="User email for scoping active session")] = "",
    current_user: Annotated[str | None, Depends(require_authenticated_user)] = None,
) -> ActiveSessionResponse:
    effective_email = current_user if current_user else user_email
    res = service.get_active_resumable_session(user_email=effective_email)
    if not res:
        return ActiveSessionResponse(session=None, questions=[])

    session, queue = res
    return ActiveSessionResponse(session=session, questions=queue)


@router.post(
    "/sessions/{session_id}/progress",
    response_model=StatusResponse,
    summary="Save session progress",
    description="Update current question index and answers list for an active session.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Session ID was not found",
            "content": {"application/json": {"example": {"detail": "Session not found: sess-123"}}},
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to modify this session",
        },
    },
)
def update_progress(
    session_id: str,
    req: UpdateProgressRequest,
    service: Annotated[PracticeService, Depends(get_practice_service)],
    current_user: Annotated[str | None, Depends(require_authenticated_user)] = None,
) -> StatusResponse:
    session = service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    _verify_session_ownership(session, current_user)

    session.current_index = req.current_index
    session.results = req.results
    session.updated_at = datetime.now(UTC).isoformat()
    service.save_session_progress(session)
    return StatusResponse(status="saved")


@router.post(
    "/sessions/{session_id}/complete",
    response_model=StatusResponse,
    summary="Complete dojo session",
    description="Mark an active dojo practice session as completed.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Session ID was not found",
            "content": {"application/json": {"example": {"detail": "Session not found: sess-123"}}},
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to modify this session",
        },
    },
)
def complete_session(
    session_id: str,
    service: Annotated[PracticeService, Depends(get_practice_service)],
    current_user: Annotated[str | None, Depends(require_authenticated_user)] = None,
) -> StatusResponse:
    session = service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    _verify_session_ownership(session, current_user)

    service.complete_session(session_id)
    return StatusResponse(status="completed")


@router.delete(
    "/sessions/{session_id}",
    response_model=StatusResponse,
    summary="Abandon dojo session",
    description="Permanently discard and delete an active or incomplete dojo practice session.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Session ID was not found",
            "content": {"application/json": {"example": {"detail": "Session not found: sess-123"}}},
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to modify this session",
        },
    },
)
def abandon_session(
    session_id: str,
    service: Annotated[PracticeService, Depends(get_practice_service)],
    current_user: Annotated[str | None, Depends(require_authenticated_user)] = None,
) -> StatusResponse:
    session = service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    _verify_session_ownership(session, current_user)

    service.abandon_session(session_id)
    return StatusResponse(status="abandoned")
