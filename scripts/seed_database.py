"""Script and utility to seed questions into Qdrant Vector Store."""

import hashlib
import logging
import math
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.interfaces import ILLMProvider, IVectorStore
from src.domain.models import ExamQuestion
from src.infrastructure.config import settings
from src.infrastructure.llm_provider import GoogleGenAIProvider
from src.infrastructure.qdrant_store import QdrantVectorStore
from src.infrastructure.question_repository import LocalQuestionRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def generate_pseudo_embedding(text: str, dim: int = 768) -> list[float]:
    """Generate deterministic normalized pseudo-embedding when API key is not present."""
    vec = []
    for i in range(dim):
        h = hashlib.sha256(f"{text}_{i}".encode()).hexdigest()
        val = (int(h[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0
        vec.append(val)
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def seed_questions(
    vector_store: IVectorStore | None = None,
    llm_provider: ILLMProvider | None = None,
    questions: list[ExamQuestion] | None = None,
) -> int:
    """Seed questions into the specified or newly instantiated vector store."""
    if questions is None:
        repo = LocalQuestionRepository()
        questions = repo.get_all_questions()

    if not questions:
        logger.warning("No questions provided to seed.")
        return 0

    store = vector_store or QdrantVectorStore()
    provider = llm_provider or GoogleGenAIProvider()

    texts_to_embed = [q.format_full_text() for q in questions]
    embeddings: list[list[float]] = []

    if settings.gemini_api_key or (
        isinstance(provider, GoogleGenAIProvider) and provider.client is not None
    ):
        try:
            logger.info("Generating embeddings via Gemini API...")
            embeddings = provider.embed_batch(
                texts=texts_to_embed,
                task_type="RETRIEVAL_DOCUMENT",
                dimensionality=settings.embedding_dimension,
            )
        except Exception as e:
            logger.warning("Gemini embedding failed (%s). Falling back to pseudo-embeddings.", e)
            embeddings = [
                generate_pseudo_embedding(t, settings.embedding_dimension) for t in texts_to_embed
            ]
    else:
        logger.info("Using deterministic pseudo-embeddings for offline development.")
        embeddings = [
            generate_pseudo_embedding(t, settings.embedding_dimension) for t in texts_to_embed
        ]

    store.upsert_exam_questions(questions, embeddings)
    logger.info("Seeded %d questions into vector store successfully.", len(questions))
    return len(questions)


def main() -> None:
    logger.info("Running seed database CLI...")
    count = seed_questions()
    logger.info("Seeding completed: %d questions indexed.", count)


if __name__ == "__main__":
    main()
