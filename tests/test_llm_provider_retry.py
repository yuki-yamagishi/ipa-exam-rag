"""Unit tests for Gemini API retry with exponential backoff and stateless fallback."""

from unittest.mock import MagicMock

import pytest
from google.genai import types

from src.domain.models import AnswerKey, ExamChoice, ExamQuestion
from src.infrastructure.llm_provider import GoogleGenAIProvider, is_transient_error


class MockAPIError(Exception):
    """Mock API error for testing."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message


@pytest.fixture
def sample_question() -> ExamQuestion:
    return ExamQuestion(
        id="2025-SA-AM2-Q01",
        exam_type="SA",
        year=2025,
        term="秋期",
        question_number=1,
        question_text="SOLID原則に関する問題",
        choices=[
            ExamChoice(key=AnswerKey.A, text="単一責任の原則"),
            ExamChoice(key=AnswerKey.I, text="オープン・クローズドの原則"),
            ExamChoice(key=AnswerKey.U, text="リスコフの置換原則"),
            ExamChoice(key=AnswerKey.E, text="依存性逆転の原則"),
        ],
        correct_answer=AnswerKey.A,
        explanation="Sは単一責任の原則です。",
        category="ソフトウェア工学",
    )


def test_is_transient_error():
    # 503 UNAVAILABLE
    assert is_transient_error(MockAPIError("503 UNAVAILABLE", code=503))
    assert is_transient_error(Exception("503 Service Unavailable"))
    assert is_transient_error(Exception("This model is currently experiencing high demand."))

    # 429 RESOURCE_EXHAUSTED (Rate limit is transient, depleted credit is NOT)
    assert is_transient_error(MockAPIError("429 RESOURCE_EXHAUSTED", code=429))
    assert not is_transient_error(
        Exception(
            "429 RESOURCE_EXHAUSTED. Your prepayment credits are depleted. Please go to AI Studio"
        )
    )

    # Standard network exception types (even with empty str(e))
    assert is_transient_error(TimeoutError())
    assert is_transient_error(ConnectionResetError())
    assert is_transient_error(ConnectionError())
    assert is_transient_error(Exception("Connection reset by peer"))
    assert is_transient_error(TimeoutError("Deadline exceeded"))

    # Non-transient errors: 4xx client errors must reject even if message has 'deadline' or 'unavailable'
    assert not is_transient_error(MockAPIError("400 Bad Request", code=400))
    assert not is_transient_error(
        MockAPIError("Invalid argument: deadline parameter must be positive", code=400)
    )
    assert not is_transient_error(
        MockAPIError("Permission denied: resource unavailable for account", code=403)
    )
    assert not is_transient_error(ValueError("Invalid argument"))


def test_scenario_1_primary_immediate_success(sample_question):
    """Scenario 1: Primary model succeeds immediately on first attempt."""
    mock_client = MagicMock()
    mock_resp = MagicMock(spec=types.GenerateContentResponse)
    mock_resp.text = "単一責任の原則（SRP）です。"
    mock_client.models.generate_content.return_value = mock_resp

    sleep_calls = []
    provider = GoogleGenAIProvider(
        api_key="test-key",
        model_generate="gemini-3.7-flash",
        model_fallback="gemini-3.5-flash-lite",
        max_retries=3,
        retry_delay_seconds=1.0,
        retry_backoff_factor=2.0,
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    provider.client = mock_client

    result = provider.chat_response(
        question=sample_question,
        dialogue_history=[],
        user_message="Sは何ですか？",
        context_chunks=[],
    )

    assert result == "単一責任の原則（SRP）です。"
    assert mock_client.models.generate_content.call_count == 1
    call_args = mock_client.models.generate_content.call_args[1]
    assert call_args["model"] == "gemini-3.7-flash"
    assert len(sleep_calls) == 0


def test_scenario_2_transient_retry_success(sample_question):
    """Scenario 2: Primary model fails once with 503, succeeds on second attempt."""
    mock_client = MagicMock()
    mock_resp = MagicMock(spec=types.GenerateContentResponse)
    mock_resp.text = "リトライ成功回答"
    mock_client.models.generate_content.side_effect = [
        MockAPIError("503 UNAVAILABLE: high demand", code=503),
        mock_resp,
    ]

    sleep_calls = []
    provider = GoogleGenAIProvider(
        api_key="test-key",
        model_generate="gemini-3.7-flash",
        model_fallback="gemini-3.5-flash-lite",
        max_retries=3,
        retry_delay_seconds=1.0,
        retry_backoff_factor=2.0,
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    provider.client = mock_client

    result = provider.chat_response(
        question=sample_question,
        dialogue_history=[],
        user_message="Sは何ですか？",
        context_chunks=[],
    )

    assert result == "リトライ成功回答"
    assert mock_client.models.generate_content.call_count == 2
    # Both calls were directed to primary model
    for call in mock_client.models.generate_content.call_args_list:
        assert call[1]["model"] == "gemini-3.7-flash"
    assert sleep_calls == [1.0]


def test_scenario_3_and_4_fallback_and_stateless_guarantee(sample_question):
    """Scenarios 3 & 4: Fallback to lightweight model when retries exhaust, and verify stateless resumption on next call."""
    mock_client = MagicMock()
    fallback_resp = MagicMock(spec=types.GenerateContentResponse)
    fallback_resp.text = "フォールバックモデルからの回答"

    next_primary_resp = MagicMock(spec=types.GenerateContentResponse)
    next_primary_resp.text = "次の質問に対するプライマリモデル回答"

    # Request 1: 3 primary failures -> 1 fallback success
    # Request 2: 1 primary success
    mock_client.models.generate_content.side_effect = [
        MockAPIError("503 UNAVAILABLE", code=503),
        MockAPIError("503 UNAVAILABLE", code=503),
        MockAPIError("503 UNAVAILABLE", code=503),
        fallback_resp,
        next_primary_resp,
    ]

    sleep_calls = []
    provider = GoogleGenAIProvider(
        api_key="test-key",
        model_generate="gemini-3.7-flash",
        model_fallback="gemini-3.5-flash-lite",
        max_retries=3,
        retry_delay_seconds=1.0,
        retry_backoff_factor=2.0,
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    provider.client = mock_client

    # Request 1 (Scenario 3: Fallback)
    res1 = provider.chat_response(
        question=sample_question,
        dialogue_history=[],
        user_message="質問1",
        context_chunks=[],
    )
    assert res1 == "フォールバックモデルからの回答"
    assert mock_client.models.generate_content.call_count == 4
    assert mock_client.models.generate_content.call_args_list[0][1]["model"] == "gemini-3.7-flash"
    assert mock_client.models.generate_content.call_args_list[1][1]["model"] == "gemini-3.7-flash"
    assert mock_client.models.generate_content.call_args_list[2][1]["model"] == "gemini-3.7-flash"
    assert (
        mock_client.models.generate_content.call_args_list[3][1]["model"] == "gemini-3.5-flash-lite"
    )
    assert sleep_calls == [1.0, 2.0]

    # Scenario 4: Verify provider.model_generate was NOT mutated
    assert provider.model_generate == "gemini-3.7-flash"

    # Request 2 (Scenario 4: Next request must start with primary model again)
    res2 = provider.chat_response(
        question=sample_question,
        dialogue_history=[],
        user_message="質問2",
        context_chunks=[],
    )
    assert res2 == "次の質問に対するプライマリモデル回答"
    assert mock_client.models.generate_content.call_count == 5
    assert mock_client.models.generate_content.call_args_list[4][1]["model"] == "gemini-3.7-flash"


def test_scenario_5_non_retryable_client_error(sample_question):
    """Scenario 5: Non-transient errors (e.g. 400 Bad Request) abort immediately without retry or fallback."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = MockAPIError("400 Bad Request", code=400)

    sleep_calls = []
    provider = GoogleGenAIProvider(
        api_key="test-key",
        model_generate="gemini-3.7-flash",
        model_fallback="gemini-3.5-flash-lite",
        max_retries=3,
        retry_delay_seconds=1.0,
        retry_backoff_factor=2.0,
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    provider.client = mock_client

    with pytest.raises(MockAPIError) as exc_info:
        provider.chat_response(
            question=sample_question,
            dialogue_history=[],
            user_message="不正なリクエスト",
            context_chunks=[],
        )

    assert "400 Bad Request" in str(exc_info.value)
    # Exactly 1 call was made (no retries, no fallback)
    assert mock_client.models.generate_content.call_count == 1
    assert len(sleep_calls) == 0


def test_scenario_6_fallback_exhaustion_immediate_raise(sample_question):
    """Scenario 6: If fallback model also fails, immediately raise without secondary retry explosion."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        MockAPIError("503 UNAVAILABLE", code=503),
        MockAPIError("503 UNAVAILABLE", code=503),
        MockAPIError("503 UNAVAILABLE", code=503),
        MockAPIError("503 UNAVAILABLE on fallback", code=503),
    ]

    sleep_calls = []
    provider = GoogleGenAIProvider(
        api_key="test-key",
        model_generate="gemini-3.7-flash",
        model_fallback="gemini-3.5-flash-lite",
        max_retries=3,
        retry_delay_seconds=1.0,
        retry_backoff_factor=2.0,
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    provider.client = mock_client

    with pytest.raises(MockAPIError) as exc_info:
        provider.chat_response(
            question=sample_question,
            dialogue_history=[],
            user_message="質問",
            context_chunks=[],
        )

    assert "503 UNAVAILABLE on fallback" in str(exc_info.value)
    # 3 primary attempts + 1 fallback attempt = 4 calls total
    assert mock_client.models.generate_content.call_count == 4
    # Sleep was called only for primary retries (2 times: after attempt 1 and 2)
    assert len(sleep_calls) == 2


def test_extract_knowledge_candidates_no_double_retry_on_api_error(sample_question):
    """Verify that batch knowledge extraction does not double-retry when API call fails."""
    mock_client = MagicMock()
    # Fail primary (3 attempts) + fail fallback (1 attempt) = 4 attempts total
    mock_client.models.generate_content.side_effect = [
        MockAPIError("503 UNAVAILABLE", code=503),
        MockAPIError("503 UNAVAILABLE", code=503),
        MockAPIError("503 UNAVAILABLE", code=503),
        MockAPIError("503 UNAVAILABLE on fallback", code=503),
    ]

    sleep_calls = []
    provider = GoogleGenAIProvider(
        api_key="test-key",
        model_generate="gemini-3.7-flash",
        model_fallback="gemini-3.5-flash-lite",
        max_retries=3,
        retry_delay_seconds=1.0,
        retry_backoff_factor=2.0,
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    provider.client = mock_client

    candidates = provider.extract_knowledge_candidates(
        question=sample_question,
        dialogue_history=[{"role": "user", "content": "SOLID原則について"}],
    )

    assert candidates == []
    # Must be exactly 4 calls (3 primary + 1 fallback), NOT 8 calls (no double retry)
    assert mock_client.models.generate_content.call_count == 4


def test_embed_success_with_genai_pydantic_response():
    """Scenario 1: embed() extracts values correctly from official google-genai EmbedContentResponse."""
    mock_client = MagicMock()
    # Real Pydantic model response returned by google-genai SDK
    mock_resp = types.EmbedContentResponse(
        embeddings=[types.ContentEmbedding(values=[0.1, 0.2, 0.3])]
    )
    mock_client.models.embed_content.return_value = mock_resp

    provider = GoogleGenAIProvider(api_key="test-key")
    provider.client = mock_client

    result = provider.embed("テスト文字列", dimensionality=768)

    assert result == [0.1, 0.2, 0.3]
    assert mock_client.models.embed_content.call_count == 1
    call_kwargs = mock_client.models.embed_content.call_args[1]
    assert call_kwargs["contents"] == "テスト文字列"


def test_embed_empty_or_invalid_raises_value_error():
    """Scenario 2: embed() raises ValueError when embeddings is empty or lacks values."""
    mock_client = MagicMock()
    # Empty embeddings list
    mock_resp = types.EmbedContentResponse(embeddings=[])
    mock_client.models.embed_content.return_value = mock_resp

    provider = GoogleGenAIProvider(api_key="test-key")
    provider.client = mock_client

    with pytest.raises(ValueError, match="Failed to retrieve embedding values from Gemini API."):
        provider.embed("空レスポンス")


def test_embed_batch_success():
    """Scenario 3: embed_batch() correctly extracts multiple embeddings."""
    mock_client = MagicMock()
    mock_resp = types.EmbedContentResponse(
        embeddings=[
            types.ContentEmbedding(values=[0.1, 0.2]),
            types.ContentEmbedding(values=[0.3, 0.4]),
        ]
    )
    mock_client.models.embed_content.return_value = mock_resp

    provider = GoogleGenAIProvider(api_key="test-key")
    provider.client = mock_client

    results = provider.embed_batch(["文1", "文2"])

    assert results == [[0.1, 0.2], [0.3, 0.4]]
    assert mock_client.models.embed_content.call_count == 1


def test_embed_batch_empty_input():
    """Scenario 4: embed_batch() returns empty list immediately for empty input without API call."""
    mock_client = MagicMock()
    provider = GoogleGenAIProvider(api_key="test-key")
    provider.client = mock_client

    results = provider.embed_batch([])

    assert results == []
    assert mock_client.models.embed_content.call_count == 0
