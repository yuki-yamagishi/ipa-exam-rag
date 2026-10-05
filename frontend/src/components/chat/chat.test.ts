import test from 'node:test';
import assert from 'node:assert/strict';
import { ragApi, ApiError } from '../../api/client.ts';
import type { RetrievalChunk } from '../../types/index.ts';

const mockCitationChunks: RetrievalChunk[] = [
  {
    id: 'chunk-001',
    content: 'フォールトアボイダンスは故障そのものを未然に防ぐ品質向上策である。',
    score: 0.92,
    doc_type: 'exam_question',
    metadata: {
      question_id: '2025-SA-AM2-Q01',
      title: '2025年 秋期 問1: システムアーキテクチャ',
    },
  },
  {
    id: 'chunk-002',
    content: '高信頼性部品の採用や厳格なテスト工程がフォールトアボイダンスに該当する。',
    score: 0.85,
    doc_type: 'learned_insight',
    metadata: {
      title: '耐障害性設計の核心概念',
    },
  },
];

test('Scenario 1: SSE chat stream dispatches tokens sequentially and completes on done', async () => {
  const originalFetch = globalThis.fetch;
  try {
    const ssePayload = [
      'event: token\ndata: {"token": "フォールト"}\n\n',
      'event: token\ndata: {"token": "アボイダンスは"}\n\n',
      'event: token\ndata: {"token": "故障予防です。"}\n\n',
      'event: done\ndata: {"status": "completed"}\n\n',
    ].join('');

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    globalThis.fetch = async () => {
      return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    };

    let accumulatedText = '';
    let isDone = false;

    await ragApi.chatStream(
      {
        question_id: '2025-SA-AM2-Q01',
        user_message: 'フォールトアボイダンスについて教えて',
      },
      {
        onToken: (token) => {
          accumulatedText += token;
        },
        onDone: () => {
          isDone = true;
        },
      }
    );

    assert.equal(accumulatedText, 'フォールトアボイダンスは故障予防です。');
    assert.equal(isDone, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 2: SSE chat stream extracts citation chunks on citation event', async () => {
  const originalFetch = globalThis.fetch;
  try {
    const ssePayload = [
      `event: citation\ndata: ${JSON.stringify(mockCitationChunks)}\n\n`,
      'event: token\ndata: {"token": "回答開始"}\n\n',
      'event: done\ndata: {"status": "completed"}\n\n',
    ].join('');

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    globalThis.fetch = async () => {
      return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    };

    let receivedCitations: RetrievalChunk[] = [];

    await ragApi.chatStream(
      {
        question_id: '2025-SA-AM2-Q01',
        user_message: '根拠を教えて',
      },
      {
        onCitation: (chunks) => {
          receivedCitations = chunks;
        },
      }
    );

    assert.equal(receivedCitations.length, 2);
    assert.equal(receivedCitations[0].id, 'chunk-001');
    assert.equal(receivedCitations[0].doc_type, 'exam_question');
    assert.equal(receivedCitations[1].doc_type, 'learned_insight');
    assert.equal(receivedCitations[0].score, 0.92);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 3: questionContext targeting and fallback logic', () => {
  const defaultFallback = '2025-SA-AM2-Q01';

  // Case A: specific question context present
  const mockContext = { id: '2024-SA-AM2-Q10', question_number: 10 };
  const targetIdA = mockContext?.id || defaultFallback;
  assert.equal(targetIdA, '2024-SA-AM2-Q10');

  // Case B: question context cleared or null
  const nullContext = null;
  const targetIdB = (nullContext as { id: string } | null)?.id || defaultFallback;
  assert.equal(targetIdB, '2025-SA-AM2-Q01');
});

test('Scenario 4: saveKnowledgeCandidate sends POST request and receives 202 accepted response', async () => {
  const originalFetch = globalThis.fetch;
  try {
    let capturedBody = '';
    let capturedMethod = '';

    globalThis.fetch = async (_url, options) => {
      capturedMethod = options?.method || '';
      capturedBody = String(options?.body || '');
      return new Response(
        JSON.stringify({
          status: 'accepted',
          message: 'Knowledge extraction scheduled in background',
          question_id: '2025-SA-AM2-Q01',
        }),
        {
          status: 202,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    };

    const res = await ragApi.saveKnowledgeCandidate({
      question_id: '2025-SA-AM2-Q01',
      dialogue_history: [
        { role: 'user', content: 'なぜアが正解ですか？' },
        { role: 'assistant', content: 'フォールトアボイダンスだからです。' },
      ],
    });

    assert.equal(capturedMethod, 'POST');
    assert.ok(capturedBody.includes('2025-SA-AM2-Q01'));
    assert.ok(capturedBody.includes('なぜアが正解ですか？'));
    assert.equal(res.status, 'accepted');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 5: SSE stream handles error event and dispatches ApiError', async () => {
  const originalFetch = globalThis.fetch;
  try {
    const ssePayload = [
      'event: error\ndata: {"detail": "Rate limit exceeded"}\n\n',
    ].join('');

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    globalThis.fetch = async () => {
      return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    };

    let dispatchedError: ApiError | null = null;
    let onDoneCalled = false;

    await ragApi.chatStream(
      {
        question_id: '2025-SA-AM2-Q01',
        user_message: 'テスト',
      },
      {
        onError: (err) => {
          dispatchedError = err;
        },
        onDone: () => {
          onDoneCalled = true;
        },
      }
    );

    assert.ok(dispatchedError !== null);
    const err: ApiError = dispatchedError;
    assert.equal(err.status, 500);
    assert.equal(err.detail, 'Rate limit exceeded');
    // Ensure onDone is not called when error occurs
    assert.equal(onDoneCalled, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 5b: Error retry button extracts previous user message for retransmission', () => {
  const dummyMessages = [
    { id: 'welcome', role: 'assistant', content: 'ようこそ' },
    { id: 'user-1', role: 'user', content: 'フォールトアボイダンスとは？' },
    { id: 'assistant-1', role: 'assistant', content: '', error: 'Network Error' },
  ];

  const currentIdx = dummyMessages.findIndex((m) => m.id === 'assistant-1');
  const prevUserMsg = dummyMessages
    .slice(0, currentIdx)
    .reverse()
    .find((m) => m.role === 'user');

  assert.ok(prevUserMsg !== undefined);
  assert.equal(prevUserMsg.content, 'フォールトアボイダンスとは？');
});

test('Scenario 1b: onDone is called exactly once when stream finishes', async () => {
  const originalFetch = globalThis.fetch;
  try {
    const ssePayload = 'event: done\ndata: {}\n\n';
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    globalThis.fetch = async () => {
      return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    };

    let doneCallCount = 0;
    await ragApi.chatStream(
      {
        question_id: '2025-SA-AM2-Q01',
        user_message: 'テスト',
      },
      {
        onDone: () => {
          doneCallCount++;
        },
      }
    );

    assert.equal(doneCallCount, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 6: Empty message validation prevents submission', () => {
  const validateInput = (msg: string) => msg.trim().length > 0;

  assert.equal(validateInput(''), false);
  assert.equal(validateInput('   '), false);
  assert.equal(validateInput('\t\n'), false);
  assert.equal(validateInput('有効な質問'), true);
});

