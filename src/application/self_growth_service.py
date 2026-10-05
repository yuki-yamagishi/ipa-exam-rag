"""Self-growth service managing closed-loop continuous learning and knowledge indexing."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from src.domain.interfaces import ILLMProvider, IVectorStore
from src.domain.models import (
    ExamQuestion,
    KnowledgeCandidate,
    KnowledgeVerificationResult,
    LearnedInsight,
)
from src.infrastructure.config import settings

logger = logging.getLogger(__name__)


class GrowthStatus(StrEnum):
    """Result status of self-growth cycle."""

    CREATED_NEW = "CREATED_NEW"
    UPDATED_EXISTING = "UPDATED_EXISTING"
    REJECTED_NO_CANDIDATE = "REJECTED_NO_CANDIDATE"
    REJECTED_JUDGE_FAILED = "REJECTED_JUDGE_FAILED"


class SelfGrowthReport(BaseModel):
    """Detailed audit report of a single candidate learning iteration."""

    status: GrowthStatus
    candidate: KnowledgeCandidate | None = None
    verification_result: KnowledgeVerificationResult | None = None
    saved_insight: LearnedInsight | None = None
    similarity_score: float = Field(
        default=0.0, description="Similarity score with existing knowledge"
    )
    message: str = ""


class MultiSelfGrowthReport(BaseModel):
    """Aggregated report of multiple extracted insights from a dialogue session."""

    reports: list[SelfGrowthReport] = Field(default_factory=list)
    created_count: int = 0
    updated_count: int = 0
    rejected_count: int = 0
    message: str = ""

    @property
    def status(self) -> GrowthStatus:
        """Primary overall status for backward compatibility."""
        if self.created_count > 0:
            return GrowthStatus.CREATED_NEW
        if self.updated_count > 0:
            return GrowthStatus.UPDATED_EXISTING
        if any(r.status == GrowthStatus.REJECTED_JUDGE_FAILED for r in self.reports):
            return GrowthStatus.REJECTED_JUDGE_FAILED
        return GrowthStatus.REJECTED_NO_CANDIDATE

    @property
    def primary_report(self) -> SelfGrowthReport | None:
        """First or most relevant report."""
        return self.reports[0] if self.reports else None

    @property
    def candidate(self) -> KnowledgeCandidate | None:
        return self.primary_report.candidate if self.primary_report else None

    @property
    def verification_result(self) -> KnowledgeVerificationResult | None:
        return self.primary_report.verification_result if self.primary_report else None

    @property
    def saved_insight(self) -> LearnedInsight | None:
        return self.primary_report.saved_insight if self.primary_report else None

    @property
    def similarity_score(self) -> float:
        return self.primary_report.similarity_score if self.primary_report else 0.0


class SelfGrowthService:
    """Orchestrator for extracting, verifying, deduplicating, and re-indexing insights."""

    def __init__(
        self,
        vector_store: IVectorStore,
        llm_provider: ILLMProvider,
        confidence_threshold: float | None = None,
        dedup_threshold: float | None = None,
    ):
        self.vector_store = vector_store
        self.llm_provider = llm_provider
        self.confidence_threshold = confidence_threshold or settings.judge_confidence_threshold
        self.dedup_threshold = dedup_threshold or settings.dedup_similarity_threshold

    def _verify_and_index_candidate(
        self,
        question: ExamQuestion,
        candidate: KnowledgeCandidate,
    ) -> SelfGrowthReport:
        """Run Judge Agent evaluation, deduplication, and indexing for a single candidate."""
        # Stage 2: Judge Agent (Factual Consistency & Gatekeeper)
        judge_result = self.llm_provider.judge_knowledge(
            candidate=candidate,
            question=question,
        )
        logger.info(
            "Judge result for '%s': approved=%s, score=%.2f",
            candidate.title,
            judge_result.is_approved,
            judge_result.confidence_score,
        )

        if (
            not judge_result.is_approved
            or judge_result.confidence_score < self.confidence_threshold
        ):
            logger.warning(
                "Insight candidate '%s' rejected by Judge: score=%.2f (threshold=%.2f)",
                candidate.title,
                judge_result.confidence_score,
                self.confidence_threshold,
            )
            return SelfGrowthReport(
                status=GrowthStatus.REJECTED_JUDGE_FAILED,
                candidate=candidate,
                verification_result=judge_result,
                message=f"審査官（Judge Agent）により却下されました (信頼度: {judge_result.confidence_score:.2f} < {self.confidence_threshold:.2f})。理由: {judge_result.critique}",
            )

        # Stage 3: Embedding with RETRIEVAL_DOCUMENT
        temp_insight = LearnedInsight(
            id="temp",
            source_question_id=question.id,
            title=judge_result.refined_title,
            core_concept=judge_result.refined_core_concept,
            trap_analysis=judge_result.refined_trap_analysis,
            practical_takeaway=candidate.practical_takeaway,
            confidence_score=judge_result.confidence_score,
            is_verified=True,
            tags=judge_result.tags or candidate.proposed_tags,
        )
        doc_text = temp_insight.format_document_text()
        embedding = self.llm_provider.embed(
            text=doc_text,
            task_type="RETRIEVAL_DOCUMENT",
            title=temp_insight.title,
        )

        # Stage 4: Deduplication & Re-Indexing
        existing_insight, sim_score = self.vector_store.find_most_similar_insight(
            query_dense_vector=embedding,
            threshold=self.dedup_threshold,
        )

        if existing_insight:
            # Update & Merge into existing insight using non-destructive model_copy
            logger.info(
                "Duplicate/similar insight found (sim=%.3f). Merging into %s",
                sim_score,
                existing_insight.id,
            )
            merged = existing_insight.model_copy(
                update={
                    "title": judge_result.refined_title,
                    "core_concept": (
                        f"{existing_insight.core_concept}\n[追加補足]: {judge_result.refined_core_concept}"
                    ),
                    "trap_analysis": (
                        f"{existing_insight.trap_analysis}\n[追加トラップ]: {judge_result.refined_trap_analysis}"
                    ),
                    "practical_takeaway": (
                        f"{existing_insight.practical_takeaway}\n[追加指針]: {candidate.practical_takeaway}"
                    ),
                    "tags": list(dict.fromkeys(existing_insight.tags + temp_insight.tags)),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "confidence_score": max(
                        existing_insight.confidence_score, judge_result.confidence_score
                    ),
                }
            )

            updated_doc_text = merged.format_document_text()
            updated_embedding = self.llm_provider.embed(
                text=updated_doc_text,
                task_type="RETRIEVAL_DOCUMENT",
                title=merged.title,
            )
            self.vector_store.upsert_insight(merged, updated_embedding)

            return SelfGrowthReport(
                status=GrowthStatus.UPDATED_EXISTING,
                candidate=candidate,
                verification_result=judge_result,
                saved_insight=merged,
                similarity_score=sim_score,
                message=f"既存知見「{merged.title}」と意味的に重複（類似度: {sim_score:.3f}）したため、既存レコードへ差分知見を安全に統合・更新しました。",
            )

        # New Insight insertion — assign final ID via non-destructive model_copy
        new_id = f"insight_{uuid.uuid4().hex[:8]}"
        final_insight = temp_insight.model_copy(update={"id": new_id})
        self.vector_store.upsert_insight(final_insight, embedding)
        logger.info(
            "Successfully indexed new insight: %s (id: %s)", final_insight.title, final_insight.id
        )

        return SelfGrowthReport(
            status=GrowthStatus.CREATED_NEW,
            candidate=candidate,
            verification_result=judge_result,
            saved_insight=final_insight,
            similarity_score=sim_score,
            message=f"新規知見「{final_insight.title}」が承認され（信頼度: {judge_result.confidence_score:.2f}）、Qdrant へ安全に再インデックスされました！",
        )

    def process_dialogue_to_knowledge(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> MultiSelfGrowthReport:
        """Run complete 4-stage closed loop self-learning pipeline supporting multiple candidates."""
        logger.info("Starting multi-candidate self-growth pipeline for question: %s", question.id)

        # Stage 1: Extractor (Multi-candidates extraction)
        candidates: list[KnowledgeCandidate] = []
        if hasattr(self.llm_provider, "extract_knowledge_candidates"):
            candidates = self.llm_provider.extract_knowledge_candidates(
                question=question,
                dialogue_history=dialogue_history,
            )

        if not candidates:
            # Fallback to single candidate extraction
            single = self.llm_provider.extract_knowledge_candidate(
                question=question,
                dialogue_history=dialogue_history,
            )
            if single:
                candidates = [single]

        if not candidates:
            logger.info("No candidate insights extracted from dialogue.")
            rep = SelfGrowthReport(
                status=GrowthStatus.REJECTED_NO_CANDIDATE,
                message="対話内容から新規の技術的知見が抽出されませんでした（一般的な質問または挨拶等）。",
            )
            return MultiSelfGrowthReport(
                reports=[rep],
                message="対話内容から新規の技術的知見が抽出されませんでした。",
            )

        # Process each candidate through Judge & Deduplication
        individual_reports: list[SelfGrowthReport] = []
        created_count = 0
        updated_count = 0
        rejected_count = 0

        for cand in candidates:
            rep = self._verify_and_index_candidate(question, cand)
            individual_reports.append(rep)
            if rep.status == GrowthStatus.CREATED_NEW:
                created_count += 1
            elif rep.status == GrowthStatus.UPDATED_EXISTING:
                updated_count += 1
            elif rep.status == GrowthStatus.REJECTED_JUDGE_FAILED:
                rejected_count += 1

        if len(candidates) == 1:
            summary_msg = individual_reports[0].message
        else:
            summary_msg = f"{len(candidates)} 件の知見候補を審査: 新規登録 {created_count} 件、既存統合 {updated_count} 件、却下 {rejected_count} 件"

        return MultiSelfGrowthReport(
            reports=individual_reports,
            created_count=created_count,
            updated_count=updated_count,
            rejected_count=rejected_count,
            message=summary_msg,
        )

    async def process_dialogue_to_knowledge_async(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        max_concurrency: int = 2,
    ) -> MultiSelfGrowthReport:
        """Run 4-stage pipeline with parallel Judge Agent verification using asyncio.Semaphore."""
        logger.info(
            "Starting parallel multi-candidate self-growth pipeline for question: %s (concurrency=%d)",
            question.id,
            max_concurrency,
        )

        def _extract() -> list[KnowledgeCandidate]:
            if hasattr(self.llm_provider, "extract_knowledge_candidates"):
                cands = self.llm_provider.extract_knowledge_candidates(
                    question=question,
                    dialogue_history=dialogue_history,
                )
                if cands:
                    return cands
            single = self.llm_provider.extract_knowledge_candidate(
                question=question,
                dialogue_history=dialogue_history,
            )
            return [single] if single else []

        candidates = await asyncio.to_thread(_extract)

        if not candidates:
            logger.info("No candidate insights extracted from dialogue.")
            rep = SelfGrowthReport(
                status=GrowthStatus.REJECTED_NO_CANDIDATE,
                message="対話内容から新規の技術的知見が抽出されませんでした（一般的な質問または挨拶等）。",
            )
            return MultiSelfGrowthReport(
                reports=[rep],
                message="対話内容から新規の技術的知見が抽出されませんでした。",
            )

        semaphore = asyncio.Semaphore(max_concurrency)

        async def _verify_worker(cand: KnowledgeCandidate) -> SelfGrowthReport:
            async with semaphore:
                try:
                    return await asyncio.to_thread(self._verify_and_index_candidate, question, cand)
                except Exception as e:
                    logger.error(
                        "Verification failed for candidate '%s': %s",
                        cand.title,
                        e,
                        exc_info=True,
                    )
                    return SelfGrowthReport(
                        status=GrowthStatus.REJECTED_JUDGE_FAILED,
                        candidate=cand,
                        message=f"審査中に内部例外が発生しました: {e}",
                    )

        individual_reports = list(await asyncio.gather(*[_verify_worker(c) for c in candidates]))

        created_count = sum(1 for r in individual_reports if r.status == GrowthStatus.CREATED_NEW)
        updated_count = sum(
            1 for r in individual_reports if r.status == GrowthStatus.UPDATED_EXISTING
        )
        rejected_count = sum(
            1 for r in individual_reports if r.status == GrowthStatus.REJECTED_JUDGE_FAILED
        )

        if len(candidates) == 1:
            summary_msg = individual_reports[0].message
        else:
            summary_msg = (
                f"{len(candidates)} 件の知見候補を並列審査: "
                f"新規登録 {created_count} 件、既存統合 {updated_count} 件、却下 {rejected_count} 件"
            )

        return MultiSelfGrowthReport(
            reports=individual_reports,
            created_count=created_count,
            updated_count=updated_count,
            rejected_count=rejected_count,
            message=summary_msg,
        )

    def list_learned_insights(self, limit: int = 50) -> list[LearnedInsight]:
        """Fetch all stored insights for inspection."""
        return self.vector_store.list_insights(limit=limit)
