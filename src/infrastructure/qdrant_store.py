"""Qdrant Vector Store implementation for IPA Exam RAG."""

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from src.domain.interfaces import IVectorStore
from src.domain.models import DocType, ExamQuestion, LearnedInsight, RetrievalChunk
from src.infrastructure.config import settings

logger = logging.getLogger(__name__)


class QdrantVectorStore(IVectorStore):
    """Qdrant client wrapper implementing IVectorStore."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        location: str | None = None,
        embedding_dimension: int | None = None,
    ):
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.embedding_dimension = embedding_dimension or settings.embedding_dimension

        # Determine connection mode: cloud, memory, or local path
        loc = location or settings.qdrant_location
        u = url or settings.qdrant_url
        k = api_key or settings.qdrant_api_key

        if loc:
            self.client = QdrantClient(location=loc)
            logger.info("Connected to Qdrant at location: %s", loc)
        elif u:
            self.client = QdrantClient(url=u, api_key=k)
            logger.info("Connected to Qdrant Cloud at: %s", u)
        else:
            # Fallback to in-memory for testing / development without cloud setup
            logger.info("No Qdrant URL or location specified. Falling back to in-memory mode.")
            self.client = QdrantClient(location=":memory:")

        # Setup collection automatically
        self.setup_collection()

    def setup_collection(self, collection_name: str | None = None) -> None:
        """Ensure collection exists and payload indexes are configured."""
        coll = collection_name or self.collection_name
        existing_collections = [c.name for c in self.client.get_collections().collections]

        if coll not in existing_collections:
            logger.info("Creating Qdrant collection: %s (dim=%d)", coll, self.embedding_dimension)
            self.client.create_collection(
                collection_name=coll,
                vectors_config=qmodels.VectorParams(
                    size=self.embedding_dimension,
                    distance=qmodels.Distance.COSINE,
                ),
            )

            # Create Payload Indexes for fast metadata filtering
            payload_indexes = [
                ("doc_type", qmodels.PayloadSchemaType.KEYWORD),
                ("exam_id", qmodels.PayloadSchemaType.KEYWORD),
                ("category", qmodels.PayloadSchemaType.KEYWORD),
                ("is_verified", qmodels.PayloadSchemaType.BOOL),
                ("source_question_id", qmodels.PayloadSchemaType.KEYWORD),
            ]
            for field_name, field_type in payload_indexes:
                try:
                    self.client.create_payload_index(
                        collection_name=coll,
                        field_name=field_name,
                        field_schema=field_type,
                    )
                except Exception as e:
                    logger.warning("Failed to create index for %s: %s", field_name, e)

    def upsert_exam_questions(
        self, questions: list[ExamQuestion], embeddings: list[list[float]]
    ) -> None:
        """Store exam questions with embeddings and metadata."""
        if len(questions) != len(embeddings):
            raise ValueError("Questions and embeddings count mismatch.")

        points = []
        for q, emb in zip(questions, embeddings, strict=True):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, q.id))
            payload: dict[str, Any] = {
                "doc_type": DocType.EXAM_QUESTION.value,
                "exam_id": f"{q.year}-{q.exam_type}-{q.term}",
                "question_id": q.id,
                "question_number": q.question_number,
                "category": q.category,
                "question_text": q.question_text,
                "choices": [c.model_dump() for c in q.choices],
                "correct_answer": q.correct_answer.value,
                "explanation": q.explanation,
                "keywords": q.keywords,
                "full_text": q.format_full_text(),
            }
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=emb,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info("Upserted %d exam questions into %s", len(points), self.collection_name)

    def upsert_insight(self, insight: LearnedInsight, embedding: list[float]) -> None:
        """Store or update a learned insight in Qdrant."""
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, insight.id))
        payload: dict[str, Any] = {
            "doc_type": DocType.LEARNED_INSIGHT.value,
            "insight_id": insight.id,
            "source_question_id": insight.source_question_id,
            "title": insight.title,
            "core_concept": insight.core_concept,
            "trap_analysis": insight.trap_analysis,
            "practical_takeaway": insight.practical_takeaway,
            "confidence_score": insight.confidence_score,
            "is_verified": insight.is_verified,
            "tags": insight.tags,
            "created_at": insight.created_at,
            "updated_at": insight.updated_at,
            "full_text": insight.format_document_text(),
        }
        point = qmodels.PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload,
        )
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point],
        )
        logger.info("Upserted learned insight: %s (id: %s)", insight.title, insight.id)

    def search_hybrid(
        self,
        query_text: str,
        query_dense_vector: list[float],
        limit: int = 5,
        filter_doc_types: list[DocType] | None = None,
    ) -> list[RetrievalChunk]:
        """Hybrid search using Qdrant query_points API with metadata filtering."""
        query_filter = None
        if filter_doc_types:
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="doc_type",
                        match=qmodels.MatchAny(any=[dt.value for dt in filter_doc_types]),
                    )
                ]
            )

        # Qdrant query_points API (Dense vector query with payload filter)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_dense_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        chunks: list[RetrievalChunk] = []
        for point in results.points:
            payload = point.payload or {}
            dt = DocType(payload.get("doc_type", DocType.EXAM_QUESTION.value))
            content = payload.get("full_text", "")
            if not content:
                content = f"{payload.get('question_text', '')}\n{payload.get('explanation', '')}"

            chunk = RetrievalChunk(
                id=str(point.id),
                content=content,
                score=point.score,
                doc_type=dt,
                metadata=payload,
            )
            chunks.append(chunk)

        return chunks

    def find_most_similar_insight(
        self, query_dense_vector: list[float], threshold: float = 0.88
    ) -> tuple[LearnedInsight | None, float]:
        """Check for existing similar insight to prevent knowledge bloat."""
        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="doc_type",
                    match=qmodels.MatchValue(value=DocType.LEARNED_INSIGHT.value),
                )
            ]
        )
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_dense_vector,
            query_filter=query_filter,
            limit=1,
            with_payload=True,
        )

        if not results.points:
            return None, 0.0

        top_point = results.points[0]
        score = top_point.score
        if score >= threshold:
            payload = top_point.payload or {}
            insight = LearnedInsight(
                id=payload.get("insight_id", str(top_point.id)),
                source_question_id=payload.get("source_question_id", ""),
                title=payload.get("title", ""),
                core_concept=payload.get("core_concept", ""),
                trap_analysis=payload.get("trap_analysis", ""),
                practical_takeaway=payload.get("practical_takeaway", ""),
                confidence_score=payload.get("confidence_score", 1.0),
                is_verified=payload.get("is_verified", True),
                tags=payload.get("tags", []),
                created_at=payload.get("created_at", ""),
                updated_at=payload.get("updated_at"),
            )
            return insight, score

        return None, score

    def list_insights(self, limit: int = 50) -> list[LearnedInsight]:
        """List all verified insights via Qdrant scroll API."""
        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="doc_type",
                    match=qmodels.MatchValue(value=DocType.LEARNED_INSIGHT.value),
                )
            ]
        )
        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        insights = []
        for r in records:
            p = r.payload or {}
            insights.append(
                LearnedInsight(
                    id=p.get("insight_id", str(r.id)),
                    source_question_id=p.get("source_question_id", ""),
                    title=p.get("title", ""),
                    core_concept=p.get("core_concept", ""),
                    trap_analysis=p.get("trap_analysis", ""),
                    practical_takeaway=p.get("practical_takeaway", ""),
                    confidence_score=p.get("confidence_score", 1.0),
                    is_verified=p.get("is_verified", True),
                    tags=p.get("tags", []),
                    created_at=p.get("created_at", ""),
                    updated_at=p.get("updated_at"),
                )
            )
        return insights

    def count(self) -> int:
        """Return the total number of points stored in the Qdrant collection."""
        try:
            res = self.client.count(collection_name=self.collection_name, exact=True)
            return res.count
        except Exception as e:
            logger.warning("Failed to get point count from Qdrant: %s", e)
            return 0
