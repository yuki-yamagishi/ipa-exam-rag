"""Analytics dashboard and weak point analysis API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.application.analytics_service import AnalyticsService
from src.domain.models import (
    CategoryStat,
    OverallStat,
    PracticeAttempt,
    WeakQuestionStat,
)
from src.presentation.api.deps import get_analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get(
    "/summary",
    response_model=OverallStat,
    summary="Get overall learning summary",
    description="Fetch overall dashboard statistics including attempt count, correct count, accuracy, and unique questions.",
)
def get_summary(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> OverallStat:
    return service.get_overall_dashboard()


@router.get(
    "/categories",
    response_model=list[CategoryStat],
    summary="Get performance stats by category",
    description="Fetch performance statistics aggregated by exam category, sorted by volume of attempts.",
)
def get_categories(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> list[CategoryStat]:
    return service.get_category_performance()


@router.get(
    "/weak-categories",
    response_model=list[CategoryStat],
    summary="Get weak categories below accuracy threshold",
    description="Fetch categories where accuracy rate is strictly below the specified threshold.",
)
def get_weak_categories(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    max_accuracy: Annotated[
        float,
        Query(
            ge=0.0,
            le=1.0,
            description="Upper threshold of accuracy rate for identifying weak categories",
        ),
    ] = 0.6,
) -> list[CategoryStat]:
    return service.get_weakest_categories(max_accuracy=max_accuracy)


@router.get(
    "/weak-questions",
    response_model=list[WeakQuestionStat],
    summary="Get weak questions needing review",
    description="Fetch questions identified as student weaknesses, enriched with original question details.",
)
def get_weak_questions(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="Maximum number of weak questions to return",
        ),
    ] = 5,
) -> list[WeakQuestionStat]:
    return service.get_weak_questions(limit=limit)


@router.get(
    "/history",
    response_model=list[PracticeAttempt],
    summary="Get recent practice attempts",
    description="Fetch recent practice attempt history sorted chronologically in descending order.",
)
def get_history(
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum number of recent attempts to return",
        ),
    ] = 20,
) -> list[PracticeAttempt]:
    return service.get_recent_attempts(limit=limit)
