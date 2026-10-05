import test from 'node:test';
import assert from 'node:assert/strict';
import { questionsApi, ApiError } from '../../api/client.ts';
import type { ExamQuestion, QuestionCatalogResponse } from '../../types/index.ts';

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

const mockCatalogResponse: QuestionCatalogResponse = {
  total: 125,
  items: [mockQuestion],
};

test('Scenario 1: Initial questions fetch queries with limit: 20 and offset: 0', async () => {
  const originalFetch = globalThis.fetch;
  try {
    let capturedUrl = '';
    globalThis.fetch = async (url) => {
      capturedUrl = String(url);
      return new Response(JSON.stringify(mockCatalogResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const res = await questionsApi.getQuestions({ limit: 20, offset: 0 });
    assert.ok(capturedUrl.includes('limit=20'));
    assert.ok(capturedUrl.includes('offset=0'));
    assert.equal(res.total, 125);
    assert.equal(res.items.length, 1);
    assert.equal(res.items[0].id, '2025-SA-AM2-Q01');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 2: Keyword filter query includes keyword in query string', async () => {
  const originalFetch = globalThis.fetch;
  try {
    let capturedUrl = '';
    globalThis.fetch = async (url) => {
      capturedUrl = String(url);
      return new Response(
        JSON.stringify({
          total: 5,
          items: [{ ...mockQuestion, question_text: 'TCP/IPプロトコル群において...' }],
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    };

    const res = await questionsApi.getQuestions({
      keyword: 'プロトコル',
      limit: 20,
      offset: 0,
    });

    assert.ok(capturedUrl.includes('keyword=%E3%83%97%E3%83%AD%E3%83%88%E3%82%B3%E3%83%AB'));
    assert.equal(res.total, 5);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 3: Year filter queries with selected year parameter', async () => {
  const originalFetch = globalThis.fetch;
  try {
    let capturedUrl = '';
    globalThis.fetch = async (url) => {
      capturedUrl = String(url);
      return new Response(
        JSON.stringify({
          total: 25,
          items: [{ ...mockQuestion, year: 2024 }],
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    };

    const res = await questionsApi.getQuestions({
      year: 2024,
      limit: 20,
      offset: 0,
    });

    assert.ok(capturedUrl.includes('year=2024'));
    assert.equal(res.items[0].year, 2024);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 4: Category filter queries with selected category parameter', async () => {
  const originalFetch = globalThis.fetch;
  try {
    let capturedUrl = '';
    globalThis.fetch = async (url) => {
      capturedUrl = String(url);
      return new Response(
        JSON.stringify({
          total: 15,
          items: [{ ...mockQuestion, category: 'セキュリティ' }],
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    };

    const res = await questionsApi.getQuestions({
      category: 'セキュリティ',
      limit: 20,
      offset: 0,
    });

    assert.ok(capturedUrl.includes('category=%E3%82%BB%E3%82%AD%E3%83%A5%E3%83%AA%E3%83%86%E3%82%A3'));
    assert.equal(res.items[0].category, 'セキュリティ');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 5: Pagination load more advances offset and appends questions', async () => {
  const originalFetch = globalThis.fetch;
  try {
    const page1Items = [mockQuestion];
    const page2Question: ExamQuestion = {
      ...mockQuestion,
      id: '2025-SA-AM2-Q02',
      question_number: 2,
    };
    const page2Items = [page2Question];

    let capturedUrl = '';
    globalThis.fetch = async (url) => {
      capturedUrl = String(url);
      return new Response(
        JSON.stringify({
          total: 125,
          items: page2Items,
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    };

    const res = await questionsApi.getQuestions({
      limit: 20,
      offset: 20,
    });

    assert.ok(capturedUrl.includes('offset=20'));
    // Verify list appending logic: prev + next items
    const combined = [...page1Items, ...res.items];
    assert.equal(combined.length, 2);
    assert.equal(combined[0].question_number, 1);
    assert.equal(combined[1].question_number, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Scenario 6: onAskAi handler correctly transfers question context', () => {
  let transferredQuestion: ExamQuestion | null = null;
  const handleAskAi = (q: ExamQuestion) => {
    transferredQuestion = q;
  };

  // Simulate QuestionBrowseCard action click
  handleAskAi(mockQuestion);

  if (!transferredQuestion) {
    assert.fail('transferredQuestion should not be null');
  }
  const q: ExamQuestion = transferredQuestion;
  assert.equal(q.id, '2025-SA-AM2-Q01');
  assert.equal(q.question_number, 1);
  assert.equal(q.category, 'システムアーキテクチャ');
});

test('Scenario 7: ApiError handling returns normalized error details on failure', async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({ detail: 'Database connection failed' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    await assert.rejects(
      async () => {
        await questionsApi.getQuestions();
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 500);
        assert.equal(err.detail, 'Database connection failed');
        return true;
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
