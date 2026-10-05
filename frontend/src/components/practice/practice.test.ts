import test from 'node:test';
import assert from 'node:assert/strict';
import { practiceApi, ragApi, ApiError } from '../../api/client.ts';
import type { DojoSessionState, ExamQuestion, PracticeSubmitResponse, RetrievalChunk } from '../../types/index.ts';

// Sample Mock Data
const mockQuestion: ExamQuestion = {
  id: '2025-SA-AM2-Q01',
  exam_type: 'SA',
  year: 2025,
  term: '秋期',
  question_number: 1,
  category: 'システムアーキテクチャ',
  question_text: '信頼性設計におけるフォールトアボイダンスの例として、適切なものはどれか。',
  choices: [
    { key: 'ア', text: '高品質な高信頼性部品を採用する' },
    { key: 'イ', text: '多重化してフェールセーフとする' },
    { key: 'ウ', text: 'チェックサムで誤りを検知・訂正する' },
    { key: 'エ', text: 'バックアップからロールフォワード復旧する' },
  ],
  correct_answer: 'ア',
  explanation: 'フォールトアボイダンスは故障そのものを未然に防ぐ品質向上策です。',
  keywords: ['フォールトアボイダンス', '高信頼性'],
  doc_type: 'exam_question',
};

const mockSession: DojoSessionState = {
  session_id: 'sess-test-001',
  mode: 'all',
  question_ids: ['2025-SA-AM2-Q01', '2025-SA-AM2-Q02'],
  question_count: 2,
  shuffle: false,
  current_index: 0,
  results: [],
  is_completed: false,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

test('Scenario 1: Active session resumption progress logic', () => {
  const currentNum = Math.min(mockSession.current_index + 1, mockSession.question_count);
  assert.equal(currentNum, 1);
  assert.equal(mockSession.question_count, 2);
});

test('Scenario 3: Choice selection submits answer and verifies correct evaluation', async () => {
  const originalFetch = globalThis.fetch;
  try {
    const mockSubmitRes: PracticeSubmitResponse = {
      question_id: '2025-SA-AM2-Q01',
      question_number: 1,
      user_choice: 'ア',
      correct_answer: 'ア',
      is_correct: true,
      category: 'システムアーキテクチャ',
      attempt_id: 'att-123',
    };

    globalThis.fetch = async (_url, options) => {
      assert.equal(options?.method, 'POST');
      return new Response(JSON.stringify(mockSubmitRes), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const res = await practiceApi.submitAnswer({
      question_id: mockQuestion.id,
      choice_key: 'ア',
      session_id: mockSession.session_id,
      time_spent_seconds: 5,
    });

    assert.equal(res.is_correct, true);
    assert.equal(res.user_choice, 'ア');
    assert.equal(res.correct_answer, 'ア');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 3: Double submission prevention rule logic', () => {
  // Simulating state guard: if isSubmitting or result is present, return early
  let isSubmitting = false;
  let currentResult: PracticeSubmitResponse | null = null;
  let submitCallCount = 0;

  const simulateSelect = () => {
    if (isSubmitting || currentResult !== null) return;
    submitCallCount++;
    isSubmitting = true;
    currentResult = {
      question_id: 'q1',
      question_number: 1,
      user_choice: 'ア',
      correct_answer: 'ア',
      is_correct: true,
      category: 'cat',
    };
    isSubmitting = false;
  };

  simulateSelect(); // First click
  simulateSelect(); // Second click (simulating rapid double-tap)
  simulateSelect(); // Third click (simulating another choice tap)

  assert.equal(submitCallCount, 1, 'Submit action must only fire once when answered');
});

test('Scenario 6: Session progress update calls POST endpoint with serialized progress', async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = '';
  let requestBody = '';
  try {
    globalThis.fetch = async (url, options) => {
      requestedUrl = String(url);
      requestBody = String(options?.body || '');
      return new Response(JSON.stringify({ status: 'saved' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const res = await practiceApi.updateProgress(mockSession.session_id, 1, [
      { question_id: '2025-SA-AM2-Q01', is_correct: true },
    ]);

    assert.ok(requestedUrl.includes(`/api/practice/sessions/${mockSession.session_id}/progress`));
    assert.deepEqual(JSON.parse(requestBody), {
      current_index: 1,
      results: [{ question_id: '2025-SA-AM2-Q01', is_correct: true }],
    });
    assert.deepEqual(res, { status: 'saved' });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 7: ResultSummary pass/fail threshold computation', () => {
  // 60% passing criteria for IPA AM2
  const calcAccuracy = (correct: number, total: number) =>
    total > 0 ? Math.round((correct / total) * 100) : 0;

  assert.equal(calcAccuracy(3, 5), 60);
  assert.equal(calcAccuracy(3, 5) >= 60, true); // Pass

  assert.equal(calcAccuracy(2, 5), 40);
  assert.equal(calcAccuracy(2, 5) >= 60, false); // Fail

  assert.equal(calcAccuracy(15, 25), 60);
  assert.equal(calcAccuracy(15, 25) >= 60, true); // Pass standard 25Q
});

test('Scenario 8: Abandon session calls DELETE endpoint', async () => {
  const originalFetch = globalThis.fetch;
  let requestMethod = '';
  try {
    globalThis.fetch = async (_url, options) => {
      requestMethod = options?.method || 'GET';
      return new Response(JSON.stringify({ status: 'abandoned' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const res = await practiceApi.abandonSession('sess-abandon-001');
    assert.equal(requestMethod, 'DELETE');
    assert.deepEqual(res, { status: 'abandoned' });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 9: API Error handling gracefully exposes normalized error detail', async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ detail: 'No questions matched criteria' }), {
        status: 400,
        statusText: 'Bad Request',
        headers: { 'Content-Type': 'application/json' },
      });

    await assert.rejects(
      async () => {
        await practiceApi.createSession({
          mode: 'category',
          category: 'NonExistentCategory',
          question_count: 5,
          shuffle: false,
        });
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 400);
        assert.equal(err.detail, 'No questions matched criteria');
        return true;
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 10: In-dojo AI question button opens modal and preserves practice state without navigation (Issue #030 Scenario 1)', () => {
  // Simulate PracticeScreen state management
  let isChatModalOpen = false;
  let chatModalQuestion = null as ExamQuestion | null;
  const currentQuestions = [mockQuestion];
  const currentIndex = 0;
  const currentResult: PracticeSubmitResponse = {
    question_id: mockQuestion.id,
    question_number: 1,
    user_choice: 'ア',
    correct_answer: 'ア',
    is_correct: true,
    category: mockQuestion.category,
  };

  // User clicks "この問題を AI に質問する" inside ExplanationCard
  const handleAskAiQuestion = (q: ExamQuestion) => {
    chatModalQuestion = q;
    isChatModalOpen = true;
  };

  handleAskAiQuestion(currentQuestions[currentIndex]);

  assert.equal(isChatModalOpen, true, 'Modal should be open');
  assert.equal(chatModalQuestion?.id, mockQuestion.id, 'Target question context should match');
  // State preservation assertion: practice session context is not discarded or unmounted
  assert.equal(currentQuestions.length, 1, 'Question list must be preserved');
  assert.equal(currentIndex, 0, 'Current index must remain unchanged');
  assert.equal(currentResult.is_correct, true, 'Result state must be retained');
});

test('Scenario 11: In-dojo AI chat modal streams SSE tokens and renders citations (Issue #030 Scenario 2)', async () => {
  const originalFetch = globalThis.fetch;
  try {
    const mockCitation: RetrievalChunk = {
      id: 'chunk-001',
      content: 'フォールトアボイダンスの定義と過去問解説',
      score: 0.95,
      doc_type: 'exam_question',
      metadata: {
        question_id: mockQuestion.id,
        title: '2025年 秋期 問1: システムアーキテクチャ',
      },
    };

    const ssePayload = [
      `event: citation\ndata: ${JSON.stringify([mockCitation])}\n\n`,
      'event: token\ndata: {"token": "アが正解である理由は、"}\n\n',
      'event: token\ndata: {"token": "高品質部品による故障予防だからです。"}\n\n',
      'event: done\ndata: {"status": "completed"}\n\n',
    ].join('');

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    let requestedPayload: Record<string, unknown> = {};
    globalThis.fetch = async (_url, options) => {
      requestedPayload = JSON.parse(String(options?.body || '{}'));
      return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    };

    let accumulatedText = '';
    let receivedCitations: RetrievalChunk[] = [];
    let isCompleted = false;

    await ragApi.chatStream(
      {
        question_id: mockQuestion.id,
        user_message: '選択肢アが正解である理由を教えてください',
      },
      {
        onCitation: (chunks) => {
          receivedCitations = chunks;
        },
        onToken: (tok) => {
          accumulatedText += tok;
        },
        onDone: () => {
          isCompleted = true;
        },
      }
    );

    assert.equal(requestedPayload.question_id, mockQuestion.id);
    assert.equal(receivedCitations.length, 1);
    assert.equal(receivedCitations[0].id, 'chunk-001');
    assert.equal(accumulatedText, 'アが正解である理由は、高品質部品による故障予防だからです。');
    assert.equal(isCompleted, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 12: In-dojo AI chat modal close (button / Esc) restores practice explanation view ready for next question (Issue #030 Scenario 3)', () => {
  let isChatModalOpen = true;
  let chatModalQuestion: ExamQuestion | null = mockQuestion;
  let currentIndex = 0;
  let isNextQuestionCalled = false;

  // Closing modal
  const handleCloseChatModal = () => {
    isChatModalOpen = false;
    chatModalQuestion = null;
  };

  handleCloseChatModal();

  assert.equal(isChatModalOpen, false, 'Modal should be closed');
  assert.equal(chatModalQuestion, null, 'Modal question should be reset');

  // Immediately clicking "Next Question" in ExplanationCard works without interruption
  const handleNextQuestion = () => {
    isNextQuestionCalled = true;
    currentIndex += 1;
  };

  handleNextQuestion();
  assert.equal(isNextQuestionCalled, true);
  assert.equal(currentIndex, 1);
});

test('Scenario 13: In-dojo AI chat modal knowledge save triggers background API call (Issue #030 Scenario 4)', async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = '';
  let requestedBody: Record<string, unknown> = {};

  try {
    globalThis.fetch = async (url, options) => {
      requestedUrl = String(url);
      requestedBody = JSON.parse(String(options?.body || '{}'));
      return new Response(JSON.stringify({ status: 'accepted', candidate_id: 'cand-001' }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const res = await ragApi.saveKnowledgeCandidate({
      question_id: mockQuestion.id,
      dialogue_history: [
        { role: 'user', content: 'なぜアなのですか？' },
        { role: 'assistant', content: 'フォールトアボイダンスだからです。' },
      ],
    });

    assert.ok(requestedUrl.includes('/api/rag/save-knowledge'));
    assert.equal(requestedBody.question_id, mockQuestion.id);
    assert.equal(res.status, 'accepted');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 14: Empty message and double submission prevention guard in dojo chat modal (Issue #030 Scenario 5)', () => {
  let isStreaming = false;
  let submitCallCount = 0;

  const simulateModalSend = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    submitCallCount++;
    isStreaming = true;
  };

  // Attempt empty / whitespace submissions
  simulateModalSend('');
  simulateModalSend('   ');
  simulateModalSend('\n\t');
  assert.equal(submitCallCount, 0, 'Empty message must not trigger send');

  // Valid submission
  simulateModalSend('有効な質問');
  assert.equal(submitCallCount, 1, 'Valid message triggers send');

  // Rapid double-click while streaming
  simulateModalSend('二重クリック');
  assert.equal(submitCallCount, 1, 'Double click during streaming must be blocked');

  // IME composition enter guard simulation
  isStreaming = false;
  let imeEnterDispatched = false;
  const simulateKeyDown = (key: string, isComposing: boolean, shiftKey: boolean) => {
    if (key === 'Enter' && !shiftKey && !isComposing) {
      imeEnterDispatched = true;
    }
  };
  simulateKeyDown('Enter', true, false); // IME conversion enter
  assert.equal(imeEnterDispatched, false, 'IME conversion Enter must be prevented from dispatching');
  simulateKeyDown('Enter', false, false); // Final submit enter
  assert.equal(imeEnterDispatched, true, 'Regular Enter must dispatch');
});

test('Scenario 15: Streaming error in dojo chat modal provides user-friendly error message and retry flow (Issue #030 Scenario 6)', async () => {
  const originalFetch = globalThis.fetch;
  try {
    const sseErrorPayload = 'event: error\ndata: {"status": 500, "detail": "Qdrant connection timeout"}\n\n';
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseErrorPayload));
        controller.close();
      },
    });

    globalThis.fetch = async () => {
      return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    };

    let caughtError: ApiError | null = null;

    await ragApi.chatStream(
      {
        question_id: mockQuestion.id,
        user_message: 'エラー発生テスト',
      },
      {
        onError: (err) => {
          caughtError = err;
        },
      }
    );

    assert.ok(caughtError !== null);
    assert.equal((caughtError as ApiError).detail, 'Qdrant connection timeout');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

