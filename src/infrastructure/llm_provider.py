"""Google GenAI SDK provider implementation with Gemini 3.7 and Embedding-2."""

import json
import logging
import time
from collections.abc import Callable, Iterator
from typing import Any

from google import genai
from google.genai import types

from src.domain.interfaces import ILLMProvider
from src.domain.models import (
    AnswerKey,
    ExamQuestion,
    KnowledgeCandidate,
    KnowledgeCandidateList,
    KnowledgeVerificationResult,
    RetrievalChunk,
)
from src.infrastructure.config import settings

logger = logging.getLogger(__name__)


def is_transient_error(e: Exception) -> bool:
    """Determine if an exception represents a transient failure eligible for retry."""
    # 1. Standard network exception types (even if str(e) is empty)
    if isinstance(e, (TimeoutError, ConnectionResetError, ConnectionError)):
        return True

    # 2. HTTP status code / SDK error code check
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code is not None:
        try:
            status_int = int(code)
            if status_int in (503, 502, 504):
                return True
            if status_int == 429:
                msg = str(e).lower()
                return "prepayment credits are depleted" not in msg
            if 400 <= status_int < 500:
                # Strictly reject all other 4xx client errors without inspecting message
                return False
        except (ValueError, TypeError):
            pass

    # 3. String content matching for SDKs wrapping errors without explicit code
    msg = str(e).lower()
    if "503" in msg or "unavailable" in msg or "high demand" in msg:
        return True
    if "429" in msg or "resource_exhausted" in msg:
        if "prepayment credits are depleted" in msg:
            return False
        return True
    if "deadline" in msg or "timeout" in msg or "connection reset" in msg:
        return True
    return False


class GoogleGenAIProvider(ILLMProvider):
    """Gemini API Provider using google-genai SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model_generate: str | None = None,
        model_fallback: str | None = None,
        model_embedding: str | None = None,
        embedding_dimension: int | None = None,
        max_retries: int | None = None,
        retry_delay_seconds: float | None = None,
        retry_backoff_factor: float | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        self.api_key = api_key or settings.gemini_api_key
        self.model_generate = model_generate or settings.gemini_model_generate
        self.model_fallback = model_fallback or settings.gemini_model_generate_fallback
        self.model_embedding = model_embedding or settings.gemini_model_embedding
        self.embedding_dimension = embedding_dimension or settings.embedding_dimension
        self.max_retries = max_retries if max_retries is not None else settings.gemini_max_retries
        self.retry_delay_seconds = (
            retry_delay_seconds
            if retry_delay_seconds is not None
            else settings.gemini_retry_delay_seconds
        )
        self.retry_backoff_factor = (
            retry_backoff_factor
            if retry_backoff_factor is not None
            else settings.gemini_retry_backoff_factor
        )
        self._sleep = sleep_fn if sleep_fn is not None else time.sleep

        if self.api_key:
            self.client: genai.Client | None = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Gemini API key is not configured. Real API calls will fail.")

    def update_api_key(self, api_key: str) -> None:
        """Dynamically update Gemini API key and reinitialize client."""
        self.api_key = api_key
        if api_key:
            self.client = genai.Client(api_key=api_key)
            logger.info("Gemini API client reinitialized with new API key.")
        else:
            self.client = None

    def _ensure_client(self) -> genai.Client:
        if not self.client:
            raise ValueError("Gemini API key is not configured. Please set GEMINI_API_KEY.")
        return self.client

    def _generate_content_with_retry_and_fallback(
        self,
        contents: Any,
        config: types.GenerateContentConfig | None = None,
    ) -> types.GenerateContentResponse:
        """Generate content using primary model with retry, falling back to lightweight model if exhausted.

        Guarantees:
        1. Always starts with primary model (self.model_generate) with exponential backoff retry.
        2. Falls back to self.model_fallback if all primary attempts fail due to transient errors.
        3. Never mutates self.model_generate, ensuring subsequent requests resume with primary model.
        4. If fallback model also fails, raises immediately without secondary retry explosion.
        5. Non-transient errors (e.g. 400 Bad Request) are raised immediately without retry.
        """
        client = self._ensure_client()
        last_error: Exception | None = None
        delay = self.retry_delay_seconds

        # 1. Primary Model Attempts with Exponential Backoff
        for attempt in range(self.max_retries):
            try:
                return client.models.generate_content(
                    model=self.model_generate,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                last_error = e
                if not is_transient_error(e):
                    logger.warning(
                        "Non-transient error from primary model %s: %s. Aborting retry.",
                        self.model_generate,
                        e,
                    )
                    raise e

                if attempt < self.max_retries - 1:
                    logger.info(
                        "Primary model %s hit transient error: %s. Retrying in %.2fs (attempt %d/%d)...",
                        self.model_generate,
                        e,
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    self._sleep(delay)
                    delay *= self.retry_backoff_factor
                else:
                    logger.warning(
                        "Primary model %s exhausted all %d retry attempts. Last error: %s",
                        self.model_generate,
                        self.max_retries,
                        e,
                    )

        # 2. Fallback Model (single attempt, stateless)
        if self.model_fallback and self.model_fallback != self.model_generate:
            logger.warning(
                "Falling back to model %s for this request (primary %s exhausted).",
                self.model_fallback,
                self.model_generate,
            )
            try:
                # Do NOT mutate self.model_generate here!
                return client.models.generate_content(
                    model=self.model_fallback,
                    contents=contents,
                    config=config,
                )
            except Exception as fallback_err:
                logger.error(
                    "Fallback model %s also failed: %s",
                    self.model_fallback,
                    fallback_err,
                )
                raise fallback_err

        if last_error:
            raise last_error
        raise RuntimeError("Generate content failed with unknown state")

    def embed(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
        title: str | None = None,
        dimensionality: int = 768,
    ) -> list[float]:
        """Generate single text embedding with MRL dimensionality control."""
        client = self._ensure_client()
        dim = dimensionality or self.embedding_dimension
        config = types.EmbedContentConfig(
            task_type=task_type,
            title=title,
            output_dimensionality=dim,
        )
        response = client.models.embed_content(
            model=self.model_embedding,
            contents=text,
            config=config,
        )
        # google-genai official schema always returns `embeddings: list[ContentEmbedding]`
        if response.embeddings and len(response.embeddings) > 0 and response.embeddings[0].values:
            return response.embeddings[0].values
        raise ValueError("Failed to retrieve embedding values from Gemini API.")

    def embed_batch(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        dimensionality: int = 768,
    ) -> list[list[float]]:
        """Batch embedding generation with MRL dimensionality control."""
        if not texts:
            return []
        client = self._ensure_client()
        dim = dimensionality or self.embedding_dimension
        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=dim,
        )
        response = client.models.embed_content(
            model=self.model_embedding,
            contents=texts,
            config=config,
        )
        embeddings_result: list[list[float]] = []
        if response.embeddings:
            for emb in response.embeddings:
                if emb.values is not None:
                    embeddings_result.append(emb.values)
        return embeddings_result

    def generate_explanation(
        self,
        question: ExamQuestion,
        user_choice: AnswerKey,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        """Generate grounded technical explanation for question attempt."""
        is_correct = user_choice == question.correct_answer

        context_blocks = []
        for i, chunk in enumerate(context_chunks, 1):
            context_blocks.append(f"[参考ナレッジ {i}] ({chunk.doc_type})\n{chunk.content}")
        context_text = "\n\n".join(context_blocks)

        prompt = f"""あなたはIPAシステムアーキテクト試験（SA）の高度指導AIです。
以下の設問に対するユーザーの解答に対して、詳細かつ論理的な解説を生成してください。

【対象設問】
{question.format_full_text()}

【公式正解】: ({question.correct_answer})
【ユーザーの選択】: ({user_choice}) {"【正解！】" if is_correct else "【不正解】"}

【公式/検索された関連知識・学習済み知見】:
{context_text}

【指示】:
1. 冒頭で正解・不正解を明確にし、正解の選択肢が正しい技術的根拠をアーキテクチャ設計原則に基づいて解説してください。
2. ユーザーが選んだ選択肢が不正解である場合、なぜそれが誤りなのか（どういうひっかけや前提違いがあるか）を具体的に指摘してください。
3. 他の誤肢についても、それぞれなぜ誤りなのか（どの用語・概念と混同しやすいか）を簡潔に解説してください。
4. 検索された「学習済み知見」がある場合はそれを引用・統合し、実務や類似問題に活きる深い洞察を提供してください。
"""

        response = self._generate_content_with_retry_and_fallback(
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            ),
        )
        return response.text or ""

    def _build_chat_prompt(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        """Build the structured prompt for chat discussion."""
        context_blocks = [
            f"[参考ナレッジ {i}]\n{chunk.content}" for i, chunk in enumerate(context_chunks, 1)
        ]
        context_text = "\n\n".join(context_blocks)

        history_text = "\n".join(
            [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in dialogue_history]
        )

        return f"""あなたはIPAシステムアーキテクト試験（SA）の学習を支援するAIアシスタントです。
対象設問に関するユーザーとの対話に回答してください。

【対象設問】
{question.format_full_text()}
公式正解: ({question.correct_answer})

【関連コンテキスト】:
{context_text}

【これまでの対話履歴】:
{history_text}

【ユーザーの最新の発言】:
{user_message}

【回答ガイドライン】:
- 受験生の疑問や誤解を解消し、システムアーキテクチャの理論と実務に裏打ちされた明快な解説を行ってください。
- 必要に応じてトレードオフ、非機能要件、類似技術との比較を交えて解説してください。
"""

    def chat_response(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> str:
        """Generate interactive discussion response."""
        prompt = self._build_chat_prompt(
            question=question,
            dialogue_history=dialogue_history,
            user_message=user_message,
            context_chunks=context_chunks,
        )
        response = self._generate_content_with_retry_and_fallback(
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            ),
        )
        return response.text or ""

    def chat_stream(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
        user_message: str,
        context_chunks: list[RetrievalChunk],
    ) -> Iterator[str]:
        """Generate interactive discussion response as streaming token generator."""
        prompt = self._build_chat_prompt(
            question=question,
            dialogue_history=dialogue_history,
            user_message=user_message,
            context_chunks=context_chunks,
        )
        client = self._ensure_client()
        response_stream = client.models.generate_content_stream(
            model=self.model_generate,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            ),
        )
        for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    def extract_knowledge_candidate(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> KnowledgeCandidate | None:
        """Extract valuable architectural insight from dialogue."""
        if not dialogue_history:
            return None

        history_text = "\n".join(
            [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in dialogue_history]
        )

        prompt = f"""以下の設問に関する対話履歴を分析し、将来の受験生やシステムアーキテクトにとって再利用価値のある「本質的知見」「誤答トラップの解明」「実務設計のポイント」を抽出してください。
単なる雑談や当たり前の知識ではなく、この設問・分野の理解を深める核心的知見を構造化してください。

【対象設問】
{question.format_full_text()}
正解: ({question.correct_answer})

【対話履歴】
{history_text}
"""

        try:
            response = self._generate_content_with_retry_and_fallback(
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=KnowledgeCandidate.model_json_schema(),
                    temperature=0.1,
                ),
            )
            if not response.text:
                return None
            data = json.loads(response.text)
            return KnowledgeCandidate.model_validate(data)
        except Exception as e:
            logger.error("Failed to extract knowledge candidate: %s", e)
            return None

    def extract_knowledge_candidates(
        self,
        question: ExamQuestion,
        dialogue_history: list[dict[str, str]],
    ) -> list[KnowledgeCandidate]:
        """Extract multiple distinct technical insights from dialogue history."""
        if not dialogue_history:
            return []

        history_text = "\n".join(
            [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in dialogue_history]
        )

        prompt = f"""以下の設問に関する対話履歴を分析し、将来の受験生やシステムアーキテクトにとって再利用価値のある技術的知見を抽出してください。
対話の中に複数の異なる独立した論点（例: 設問の核心概念、特定の誤肢のひっかけ分析、実務アーキテクチャへの応用など）が含まれる場合は、それぞれを個別の知見候補として分割し、リスト形式で抽出してください（最大3〜5件）。
単なる雑談、挨拶、または当たり前すぎる辞書的定義は含めないでください。知見がない場合は空リストとしてください。

【対象設問】
{question.format_full_text()}
正解: ({question.correct_answer})

【対話履歴】
{history_text}
"""

        try:
            response = self._generate_content_with_retry_and_fallback(
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=KnowledgeCandidateList.model_json_schema(),
                    temperature=0.1,
                ),
            )
        except Exception as e:
            logger.error("API call failed during batch knowledge extraction: %s", e)
            return []

        if not response.text:
            return []

        try:
            data = json.loads(response.text)
            parsed = KnowledgeCandidateList.model_validate(data)
            return parsed.candidates
        except Exception as e:
            logger.warning(
                "Failed to parse batch candidates JSON, falling back to single extraction: %s", e
            )
            # Fallback to single candidate extraction ONLY if JSON parsing fails, not on API connection failure
            single = self.extract_knowledge_candidate(question, dialogue_history)
            return [single] if single else []

    def judge_knowledge(
        self,
        candidate: KnowledgeCandidate,
        question: ExamQuestion,
    ) -> KnowledgeVerificationResult:
        """Strictly evaluate knowledge candidate with Pydantic structured output."""
        prompt = f"""あなたはIPA試験の厳格な審査官（Judge Agent）です。
抽出された知見候補が、IPAシステムアーキテクト試験のシラバス、設問の公式正解、およびコンピュータサイエンスの真理と整合しているかを厳格に審査してください。

【審査基準】:
1. 事実適合性 (Truthfulness): ハルシネーションや不正確な技術説明が含まれていないか。
2. 整合性 (Consistency): 設問の公式正解 ({question.correct_answer}) と矛盾していないか。
3. 有用性 (Utility): 単なる当たり前の定義の繰り返しではなく、受験生の理解や誤答防止に寄与するか。
4. 判定基準: 信頼度スコア (confidence_score) が 0.85 以上のもののみ is_approved = true とすること。疑問点や誤りがある場合は is_approved = false とし、critique に理由を詳述すること。

【対象設問】
{question.format_full_text()}
正解: ({question.correct_answer})

【検証対象の知見候補】
タイトル: {candidate.title}
核心概念: {candidate.core_concept}
誤答トラップ分析: {candidate.trap_analysis}
実務指針: {candidate.practical_takeaway}
対話文脈: {candidate.dialogue_context}
"""

        response = self._generate_content_with_retry_and_fallback(
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=KnowledgeVerificationResult.model_json_schema(),
                temperature=0.0,
            ),
        )

        if not response.text:
            raise ValueError("Empty response from Judge Agent")

        data = json.loads(response.text)
        return KnowledgeVerificationResult.model_validate(data)
