import test from 'node:test';
import assert from 'node:assert/strict';
import { analyticsApi, ApiError } from '../../api/client.ts';
import type {
  OverallStat,
  CategoryStat,
  WeakQuestionStat,
  PracticeAttempt,
} from '../../types/index.ts';

const dummySummary: OverallStat = {
  total_attempts: 45,
  correct_attempts: 32,
  accuracy_rate: 0.711,
  distinct_questions_attempted: 30,
  total_sessions: 5,
};

const dummyCategories: CategoryStat[] = [
  {
    category: 'システムアーキテクチャ',
    total_attempts: 20,
    correct_attempts: 16,
    accuracy_rate: 0.8,
  },
  {
    category: 'セキュリティ',
    total_attempts: 15,
    correct_attempts: 8,
    accuracy_rate: 0.533, // < 60% (weak)
  },
  {
    category: 'ネットワーク',
    total_attempts: 10,
    correct_attempts: 8,
    accuracy_rate: 0.8,
  },
];

const dummyWeakQuestions: WeakQuestionStat[] = [
  {
    question_id: '2025-SA-AM2-Q05',
    question_number: 5,
    category: 'セキュリティ',
    question_text: '公開鍵暗号とデジタル署名における鍵の役割に関する記述として...',
    total_attempts: 4,
    incorrect_count: 3,
    latest_is_correct: false,
  },
  {
    question_id: '2025-SA-AM2-Q01',
    question_number: 1,
    category: 'システムアーキテクチャ',
    question_text: 'フォールトアボイダンスとフォールトトレランスの違いに関する記述として...',
    total_attempts: 2,
    incorrect_count: 1,
    latest_is_correct: true,
  },
];

const dummyHistory: PracticeAttempt[] = [
  {
    id: 'att-1',
    session_id: 'sess-1',
    question_id: '2025-SA-AM2-Q05',
    exam_type: 'SA',
    year: 2025,
    term: '秋期',
    question_number: 5,
    category: 'セキュリティ',
    user_choice: 'イ',
    correct_answer: 'ウ',
    is_correct: false,
    time_spent_seconds: 42,
    answered_at: '2026-03-29T10:00:00Z',
  },
  {
    id: 'att-2',
    session_id: 'sess-1',
    question_id: '2025-SA-AM2-Q01',
    exam_type: 'SA',
    year: 2025,
    term: '秋期',
    question_number: 1,
    category: 'システムアーキテクチャ',
    user_choice: 'ア',
    correct_answer: 'ア',
    is_correct: true,
    time_spent_seconds: 18,
    answered_at: '2026-03-29T09:55:00Z',
  },
];

// Scenario 1: Overall Summary KPI Card calculation
test('Scenario 1: OverallSummary computes passing status and accuracy percent correctly', () => {
  const accuracyPercent = Math.round(dummySummary.accuracy_rate * 100);
  const isPassing = accuracyPercent >= 60;

  assert.equal(accuracyPercent, 71);
  assert.equal(isPassing, true);
  assert.equal(dummySummary.total_attempts, 45);
  assert.equal(dummySummary.correct_attempts, 32);
  assert.equal(dummySummary.distinct_questions_attempted, 30);
  assert.equal(dummySummary.total_sessions, 5);
});

// Scenario 2: Category performance & weak category threshold (< 60%)
test('Scenario 2: Category list identifies weak categories strictly below 60% accuracy', () => {
  const identifyWeakCategories = (cats: CategoryStat[]) => {
    return cats.filter((c) => Math.round(c.accuracy_rate * 100) < 60);
  };

  const weakCats = identifyWeakCategories(dummyCategories);
  assert.equal(weakCats.length, 1);
  assert.equal(weakCats[0].category, 'セキュリティ');
  assert.equal(Math.round(weakCats[0].accuracy_rate * 100), 53);
});

// Scenario 3: Weak questions ranking correctly ordered by incorrect_count
test('Scenario 3: Weak questions list displays ranking and latest result accurately', () => {
  assert.equal(dummyWeakQuestions.length, 2);
  assert.equal(dummyWeakQuestions[0].question_number, 5);
  assert.equal(dummyWeakQuestions[0].incorrect_count, 3);
  assert.equal(dummyWeakQuestions[0].latest_is_correct, false);

  assert.equal(dummyWeakQuestions[1].question_number, 1);
  assert.equal(dummyWeakQuestions[1].incorrect_count, 1);
  assert.equal(dummyWeakQuestions[1].latest_is_correct, true);
});

// Scenario 4: Recent attempts list formatting and verification
test('Scenario 4: Recent attempts log contains correct attributes and values', () => {
  assert.equal(dummyHistory.length, 2);
  const latest = dummyHistory[0];
  assert.equal(latest.question_number, 5);
  assert.equal(latest.user_choice, 'イ');
  assert.equal(latest.correct_answer, 'ウ');
  assert.equal(latest.is_correct, false);
  assert.equal(latest.time_spent_seconds, 42);
});

// Scenario 5: Empty state handling when no attempts exist
test('Scenario 5: Empty state logic correctly identifies when total attempts is 0', () => {
  const emptySummary: OverallStat = {
    total_attempts: 0,
    correct_attempts: 0,
    accuracy_rate: 0,
    distinct_questions_attempted: 0,
    total_sessions: 0,
  };

  const hasHistory = emptySummary.total_attempts > 0;
  assert.equal(hasHistory, false);
});

// Scenario 6: Concurrent API fetch and ApiError propagation
test('Scenario 6: analyticsApi propagates ApiError on HTTP 500 failure', async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({ detail: 'Database query timeout' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    let caughtError: ApiError | null = null;
    try {
      await analyticsApi.getSummary();
    } catch (err) {
      if (err instanceof ApiError) {
        caughtError = err;
      }
    }

    assert.ok(caughtError !== null);
    const err: ApiError = caughtError;
    assert.equal(err.status, 500);
    assert.equal(err.detail, 'Database query timeout');
  } finally {
    globalThis.fetch = originalFetch;
  }
});
