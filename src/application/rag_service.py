"""RAG service orchestrating retrieval and grounded explanation generation."""

import logging
from collections.abc import Iterator

from src.domain.interfaces import ILLMProvider, IQuestionRepository, IVectorStore
from src.domain.models import AnswerKey, DocType, ExamQuestion, RetrievalChunk

logger = logging.getLogger(__name__)


class RAGService:
    """Service providing search retrieval and grounded AI explanation."""

    def __init__(
        self,
        vector_store: IVectorStore,
        llm_provider: ILLMProvider,
        question_repo: IQuestionRepository,
    ):
        self.vector_store = vector_store
        self.llm_provider = llm_provider
        self.question_repo = question_repo

    def retrieve_context(
        self,
        query: str,
        limit: int = 4,
        filter_doc_types: list[DocType] | None = None,
    ) -> list[RetrievalChunk]:
        """Generate query vector with task_type='RETRIEVAL_QUERY' and execute hybrid search."""
        try:
            query_vector = self.llm_provider.embed(
                text=query,
                task_type="RETRIEVAL_QUERY",
            )
            return self.vector_store.search_hybrid(
                query_text=query,
                query_dense_vector=query_vector,
                limit=limit,
                filter_doc_types=filter_doc_types,
            )
        except Exception as e:
            logger.error("Context retrieval failed: %s. Returning empty context.", e)
            return []

    def explain_with_context(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
    ) -> tuple[str, list[RetrievalChunk]]:
        """Retrieve relevant knowledge and generate explanation, returning both text and citations."""
        query = f"{question.question_text} {question.category} {' '.join(question.keywords)}"
        context_chunks = self.retrieve_context(query=query, limit=4)

        try:
            explanation = self.llm_provider.generate_explanation(
                question=question,
                user_choice=user_choice,
                context_chunks=context_chunks,
            )
        except Exception as e:
            logger.error("Explanation generation failed: %s", e)
            explanation = (
                f"【公式正解】: ({question.correct_answer})\n\n"
                f"【公式解説】:\n{question.explanation}\n\n"
                f"(注: LLM API の接続が利用できないため、組み込み解説を表示しています: {e})"
            )
        return explanation, context_chunks

    def generate_explanation(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
    ) -> str:
        """Retrieve relevant knowledge (official questions + learned insights) and explain."""
        explanation, _ = self.explain_with_context(question=question, user_choice=user_choice)
        return explanation

    def ensure_seeded(self) -> int:
        """Ensure vector store has initial exam questions seeded if empty. Return seeded count."""
        try:
            current_count = self.vector_store.count()
            if current_count > 0:
                logger.info(
                    "Vector store already contains %d points. Skipping auto-seed.", current_count
                )
                return 0

            logger.info("Vector store is empty (count=0). Seeding initial exam questions...")
            questions = self.question_repo.get_all_questions()
            if not questions:
                logger.warning("No questions found in question repository to seed.")
                return 0

            texts = [q.format_full_text() for q in questions]
            embeddings = self.llm_provider.embed_batch(texts=texts, task_type="RETRIEVAL_DOCUMENT")
            self.vector_store.upsert_exam_questions(questions=questions, embeddings=embeddings)
            logger.info("Successfully seeded %d exam questions into vector store.", len(questions))
            return len(questions)
        except Exception as e:
            logger.error("Failed to automatically seed vector store: %s", e)
            return 0

    def reindex_all(self) -> int:
        """Re-embed and upsert all questions into vector store. Return reindexed count."""
        questions = self.question_repo.get_all_questions()
        if not questions:
            logger.warning("No questions found in question repository to reindex.")
            return 0
        texts = [q.format_full_text() for q in questions]
        embeddings = self.llm_provider.embed_batch(texts=texts, task_type="RETRIEVAL_DOCUMENT")
        self.vector_store.upsert_exam_questions(questions=questions, embeddings=embeddings)
        logger.info("Successfully reindexed %d exam questions into vector store.", len(questions))
        return len(questions)

    def chat_discuss(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
    ) -> str:
        """Answer interactive user questions grounded on question context and learned insights."""
        try:
            context_chunks = self.retrieve_context(
                query=f"{question.question_text} {user_message}",
                limit=4,
            )
            return self.llm_provider.chat_response(
                question=question,
                dialogue_history=dialogue_history,
                user_message=user_message,
                context_chunks=context_chunks,
            )
        except Exception as e:
            logger.error("Chat response generation failed: %s", e)
            return f"恐れ入ります。現在 AI の対話機能に一時的な問題が発生しています ({e})。公式解説をご確認ください: {question.explanation}"

    def chat_stream_with_context(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        limit: int = 4,
    ) -> tuple[list[RetrievalChunk], Iterator[str]]:
        """Retrieve relevant context chunks and return citations alongside token stream iterator."""
        context_chunks = self.retrieve_context(
            query=f"{question.question_text} {user_message}",
            limit=limit,
        )
        stream_iter = self.llm_provider.chat_stream(
            question=question,
            dialogue_history=dialogue_history,
            user_message=user_message,
            context_chunks=context_chunks,
        )
        return context_chunks, stream_iter
