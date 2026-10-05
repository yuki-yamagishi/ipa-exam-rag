"""Question catalog API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.domain.interfaces import IQuestionRepository
from src.domain.models import ExamQuestion
from src.presentation.api.deps import get_question_repository

router = APIRouter(prefix="/api/questions", tags=["questions"])


class PaginatedQuestionsResponse(BaseModel):
    """Paginated response containing exam questions and pagination metadata."""

    total: int = Field(..., description="Total number of matching questions")
    items: list[ExamQuestion] = Field(..., description="List of questions in current page")
    limit: int = Field(..., description="Page size limit")
    offset: int = Field(..., description="Page offset")


def filter_questions(
    questions: list[ExamQuestion],
    year: int | None = None,
    category: str | None = None,
    keyword: str | None = None,
) -> list[ExamQuestion]:
    """Filter questions by year, category, and keyword across text, explanation, choices, and keywords."""
    res = questions
    if year is not None:
        res = [q for q in res if q.year == year]
    if category is not None and category != "すべて":
        res = [q for q in res if q.category == category]
    if keyword and keyword.strip():
        kw = keyword.strip().lower()
        res = [
            q
            for q in res
            if kw in q.question_text.lower()
            or kw in q.explanation.lower()
            or any(kw in c.text.lower() for c in q.choices)
            or any(kw in k.lower() for k in q.keywords)
        ]
    return res


@router.get(
    "",
    response_model=PaginatedQuestionsResponse,
    summary="List and search exam questions",
    description="Retrieve questions with optional 3-axis filtering (year, category, keyword) and pagination.",
)
def list_questions(
    repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
    year: Annotated[int | None, Query(description="Filter by exam year (e.g. 2025)")] = None,
    category: Annotated[
        str | None, Query(description="Filter by category (e.g. テクノロジ系)")
    ] = None,
    keyword: Annotated[
        str | None, Query(description="Search keyword in text, choices, explanation, and tags")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> PaginatedQuestionsResponse:
    all_questions = repo.get_all_questions()
    filtered = filter_questions(all_questions, year=year, category=category, keyword=keyword)
    total = len(filtered)
    page_items = filtered[offset : offset + limit]

    return PaginatedQuestionsResponse(
        total=total,
        items=page_items,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/years",
    response_model=list[int],
    summary="Get available exam years",
    description="Retrieve all unique exam years present in the dataset in descending order.",
)
def get_years(
    repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
) -> list[int]:
    return repo.get_available_years()


@router.get(
    "/categories",
    response_model=list[str],
    summary="Get available exam categories",
    description="Retrieve all unique syllabus categories present in the dataset.",
)
def get_categories(
    repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
) -> list[str]:
    all_questions = repo.get_all_questions()
    categories = sorted({q.category for q in all_questions if q.category})
    return categories


@router.get(
    "/{question_id}",
    response_model=ExamQuestion,
    summary="Get question detail by ID",
    description="Retrieve complete question details by ID (e.g. 2025-SA-AM2-Q01).",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Question ID was not found",
            "content": {
                "application/json": {"example": {"detail": "Question not found: 2025-SA-AM2-Q99"}}
            },
        }
    },
)
def get_question(
    question_id: str,
    repo: Annotated[IQuestionRepository, Depends(get_question_repository)],
) -> ExamQuestion:
    question = repo.get_question_by_id(question_id)
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {question_id}",
        )
    return question
