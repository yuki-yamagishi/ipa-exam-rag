import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, questionsApi, practiceApi, analyticsApi } from './client.ts';

test('ApiError should properly encapsulate status and detail (Scenario 7)', () => {
  const err404 = new ApiError(404, 'Question not found', { detail: 'Question not found' });
  assert.equal(err404.status, 404);
  assert.equal(err404.detail, 'Question not found');
  assert.equal(err404.name, 'ApiError');
  assert.equal(err404.message, 'API Error 404: Question not found');
  assert.deepEqual(err404.data, { detail: 'Question not found' });

  const errNetwork = new ApiError(0, 'Network connection failed: Failed to fetch');
  assert.equal(errNetwork.status, 0);
  assert.ok(errNetwork.message.includes('Network connection failed'));
});

test('request helper should throw ApiError on HTTP 4xx/5xx responses with parsed detail', async () => {
  const originalFetch = globalThis.fetch;
  try {
    // Mock 404 with JSON detail
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ detail: 'Session not found: sess-999' }), {
        status: 404,
        statusText: 'Not Found',
        headers: { 'Content-Type': 'application/json' },
      });

    await assert.rejects(
      async () => {
        await practiceApi.updateProgress('sess-999', 1);
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 404);
        assert.equal(err.detail, 'Session not found: sess-999');
        return true;
      }
    );

    // Mock 500 with non-JSON response
    globalThis.fetch = async () =>
      new Response('<html>Internal Server Error</html>', {
        status: 500,
        statusText: 'Internal Server Error',
        headers: { 'Content-Type': 'text/html' },
      });

    await assert.rejects(
      async () => {
        await analyticsApi.getSummary();
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 500);
        assert.equal(err.detail, 'HTTP 500 Internal Server Error');
        return true;
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('request helper should convert network errors to ApiError with status 0', async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => {
      throw new Error('Connection refused');
    };

    await assert.rejects(
      async () => {
        await questionsApi.getYears();
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 0);
        assert.ok(err.detail.includes('Network connection failed: Connection refused'));
        return true;
      }
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('questionsApi.getQuestions should preserve offset: 0 in query string', async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = '';
  try {
    globalThis.fetch = async (url) => {
      requestedUrl = String(url);
      return new Response(JSON.stringify({ total: 0, items: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    await questionsApi.getQuestions({ offset: 0, limit: 10 });
    assert.ok(requestedUrl.includes('offset=0'), `Expected offset=0 in ${requestedUrl}`);
    assert.ok(requestedUrl.includes('limit=10'), `Expected limit=10 in ${requestedUrl}`);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('practiceApi.updateProgress should use POST method and send body', async () => {
  const originalFetch = globalThis.fetch;
  let requestMethod = '';
  let requestBody = '';
  try {
    globalThis.fetch = async (_url, options) => {
      requestMethod = options?.method || 'GET';
      requestBody = String(options?.body || '');
      return new Response(JSON.stringify({ status: 'saved' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const res = await practiceApi.updateProgress('sess-100', 3, [{ q: 1 }]);
    assert.equal(requestMethod, 'POST');
    assert.deepEqual(JSON.parse(requestBody), { current_index: 3, results: [{ q: 1 }] });
    assert.deepEqual(res, { status: 'saved' });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
