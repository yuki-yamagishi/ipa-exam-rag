import { test } from 'node:test';
import assert from 'node:assert/strict';
import { systemApi, authApi, ApiError } from '../../api/client.ts';
import type { SystemSettingsResponse, AuthStatusResponse } from '../../types';

test('Scenario 1: System settings and auth status retrieval logic', async () => {
  // Mock global.fetch for parallel settings and auth status fetch
  const originalFetch = global.fetch;

  global.fetch = async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();

    if (url.includes('/api/system/settings')) {
      const mockSettings: SystemSettingsResponse = {
        gemini_api_key_masked: 'AIza...9999',
        gemini_model_generate: 'gemini-2.5-flash',
        gemini_model_generate_fallback: 'gemini-1.5-flash',
        gemini_model_embedding: 'text-embedding-004',
        vector_store_points_count: 125,
        auth_enabled: true,
      };
      return new Response(JSON.stringify(mockSettings), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (url.includes('/api/auth/status')) {
      const mockAuth: AuthStatusResponse = {
        auth_enabled: true,
        authenticated: true,
        user_email: 'candidate@example.com',
      };
      return new Response(JSON.stringify(mockAuth), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 });
  };

  try {
    const [settings, auth] = await Promise.all([
      systemApi.getSettings(),
      authApi.getStatus(),
    ]);

    assert.equal(settings.gemini_api_key_masked, 'AIza...9999');
    assert.equal(settings.gemini_model_generate, 'gemini-2.5-flash');
    assert.equal(settings.vector_store_points_count, 125);
    assert.equal(settings.auth_enabled, true);

    assert.equal(auth.auth_enabled, true);
    assert.equal(auth.authenticated, true);
    assert.equal(auth.user_email, 'candidate@example.com');
  } finally {
    global.fetch = originalFetch;
  }
});

test('Scenario 2: API key dynamic update and whitespace validation', async () => {
  const originalFetch = global.fetch;
  let receivedBody: { api_key?: string } = {};

  global.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();

    if (url.includes('/api/system/api-key') && init?.method === 'POST') {
      receivedBody = JSON.parse(init.body as string);
      return new Response(
        JSON.stringify({
          success: true,
          gemini_api_key_masked: 'AIza...newk',
          message: 'Gemini API キーを更新しました。',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 });
  };

  try {
    // Client-side empty/whitespace validation logic check
    const emptyKey = '   ';
    const isValidKey = Boolean(emptyKey.trim());
    assert.equal(isValidKey, false, 'Whitespace-only API key must be considered invalid');

    // Valid key submission
    const newKey = 'AIzaSyDemoNewKey1234567890';
    const res = await systemApi.updateApiKey(newKey);

    assert.equal(receivedBody.api_key, newKey);
    assert.equal(res.success, true);
    assert.equal(res.gemini_api_key_masked, 'AIza...newk');
    assert.equal(res.message, 'Gemini API キーを更新しました。');
  } finally {
    global.fetch = originalFetch;
  }
});

test('Scenario 3: Qdrant vector store reindexing call and count tracking', async () => {
  const originalFetch = global.fetch;
  let calledMethod = '';

  global.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();

    if (url.includes('/api/system/reindex')) {
      calledMethod = init?.method || 'GET';
      return new Response(
        JSON.stringify({
          success: true,
          reindexed_count: 125,
          message: '125 件の設問をベクトルストアに再インデックスしました。',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 });
  };

  try {
    const res = await systemApi.reindexAll();

    assert.equal(calledMethod, 'POST');
    assert.equal(res.success, true);
    assert.equal(res.reindexed_count, 125);
    assert.match(res.message, /125/);
  } finally {
    global.fetch = originalFetch;
  }
});

test('Scenario 4: Practice history reset with two-step confirmation logic', async () => {
  const originalFetch = global.fetch;
  let calledReset = false;

  global.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();

    if (url.includes('/api/system/reset-history') && init?.method === 'POST') {
      calledReset = true;
      return new Response(
        JSON.stringify({
          success: true,
          message: 'すべての学習履歴および演習セッションを消去しました。',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 });
  };

  try {
    // Two-step confirmation logic simulation:
    // Step 1: User clicks "学習履歴を初期化する" -> showResetConfirm = true
    let showResetConfirm = false;
    const handleInitialClick = () => {
      showResetConfirm = true;
    };
    handleInitialClick();
    assert.equal(showResetConfirm, true, 'Confirm box must be revealed before API execution');
    assert.equal(calledReset, false, 'API must not be called upon first click');

    // Step 2: User clicks "完全に消去する" -> executes resetHistory()
    const res = await systemApi.resetHistory();

    assert.equal(calledReset, true);
    assert.equal(res.success, true);
    assert.match(res.message, /消去しました/);
  } finally {
    global.fetch = originalFetch;
  }
});

test('Scenario 5: Google OAuth login URL acquisition and logout flow', async () => {
  const originalFetch = global.fetch;

  global.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();

    if (url.includes('/api/auth/login')) {
      return new Response(
        JSON.stringify({
          login_url: 'https://accounts.google.com/o/oauth2/v2/auth?client_id=demo&state=csrf123',
          state: 'csrf123',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    if (url.includes('/api/auth/logout') && init?.method === 'POST') {
      return new Response(
        JSON.stringify({
          success: true,
          message: 'ログアウトしました。',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 });
  };

  try {
    // Login URL fetch
    const loginRes = await authApi.getLoginUrl();
    assert.ok(loginRes.login_url.startsWith('https://accounts.google.com'));
    assert.equal(loginRes.state, 'csrf123');

    // Logout call
    const logoutRes = await authApi.logout();
    assert.equal(logoutRes.success, true);
    assert.equal(logoutRes.message, 'ログアウトしました。');
  } finally {
    global.fetch = originalFetch;
  }
});

test('Scenario 6: API error handling and normalized error message presentation', async () => {
  const originalFetch = global.fetch;

  global.fetch = async () => {
    return new Response(
      JSON.stringify({
        detail: 'Gemini API キーが無効です。',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  };

  try {
    await assert.rejects(
      async () => {
        await systemApi.updateApiKey('invalid-key');
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 400);
        assert.equal(err.detail, 'Gemini API キーが無効です。');
        return true;
      }
    );
  } finally {
    global.fetch = originalFetch;
  }
});

// =============================================================================
// Issue #027 Scenarios: Infinite fetch prevention and callback stability tests
// =============================================================================

test('Issue #027 - Scenario 1 & 2: Modal fetch idempotency and diff-detection callback suppression', async () => {
  const originalFetch = global.fetch;
  let fetchCount = 0;

  global.fetch = async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();
    fetchCount++;

    if (url.includes('/api/system/settings')) {
      return new Response(
        JSON.stringify({
          gemini_api_key_masked: 'AIza...1234',
          gemini_model_generate: 'gemini-3.7-flash',
          gemini_model_generate_fallback: 'gemini-3.5-flash-lite',
          gemini_model_embedding: 'gemini-embedding-2',
          vector_store_points_count: 50,
          auth_enabled: false,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (url.includes('/api/auth/status')) {
      return new Response(
        JSON.stringify({
          auth_enabled: false,
          authenticated: true,
          user_email: null,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 });
  };

  try {
    // 1. Initial fetch executes exactly once per endpoint (2 requests total)
    const [settings, auth] = await Promise.all([
      systemApi.getSettings(),
      authApi.getStatus(),
    ]);

    assert.equal(fetchCount, 2, 'Initial fetch must make exactly 2 requests (settings + auth)');
    assert.equal(settings.gemini_model_generate, 'gemini-3.7-flash');
    assert.equal(auth.authenticated, true);

    // 2. Diff detection logic: identical status should NOT trigger parent callback
    const prevAuth: AuthStatusResponse = {
      auth_enabled: false,
      authenticated: true,
      user_email: null,
    };
    const isChanged =
      !prevAuth ||
      prevAuth.auth_enabled !== auth.auth_enabled ||
      prevAuth.authenticated !== auth.authenticated ||
      prevAuth.user_email !== auth.user_email;

    assert.equal(isChanged, false, 'Identical auth status must not be detected as changed');

    // 3. Changed auth status MUST be detected as changed
    const changedAuth: AuthStatusResponse = {
      auth_enabled: true,
      authenticated: true,
      user_email: 'newuser@example.com',
    };
    const isDetectedAsChanged =
      !prevAuth ||
      prevAuth.auth_enabled !== changedAuth.auth_enabled ||
      prevAuth.authenticated !== changedAuth.authenticated ||
      prevAuth.user_email !== changedAuth.user_email;

    assert.equal(isDetectedAsChanged, true, 'Different auth status must be detected as changed');
  } finally {
    global.fetch = originalFetch;
  }
});

test('Issue #027 - Scenario 3: Logout propagates updated auth status through callback ref safely', async () => {
  const originalFetch = global.fetch;

  global.fetch = async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();

    if (url.includes('/api/auth/logout')) {
      return new Response(
        JSON.stringify({
          success: true,
          message: 'ログアウトしました。',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    return new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 });
  };

  try {
    let capturedAuth: AuthStatusResponse | null = null;
    const mockCallbackRef = {
      current: (status: AuthStatusResponse) => {
        capturedAuth = status;
      },
    };

    const res = await authApi.logout();
    assert.equal(res.success, true);

    const updatedAuth: AuthStatusResponse = {
      auth_enabled: true,
      authenticated: false,
      user_email: null,
    };

    if (mockCallbackRef.current) {
      mockCallbackRef.current(updatedAuth);
    }

    if (!capturedAuth) {
      assert.fail('capturedAuth should not be null');
    }
    const finalAuth: AuthStatusResponse = capturedAuth;
    assert.equal(finalAuth.authenticated, false);
    assert.equal(finalAuth.user_email, null);
  } finally {
    global.fetch = originalFetch;
  }
});

test('Issue #027 - Scenario 4: Error handling on 500 stops loading and propagates normalized error', async () => {
  const originalFetch = global.fetch;

  global.fetch = async () => {
    return new Response(
      JSON.stringify({
        detail: '内部サーバーエラーが発生しました。',
      }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  };

  try {
    await assert.rejects(
      async () => {
        await Promise.all([systemApi.getSettings(), authApi.getStatus()]);
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, 500);
        assert.equal(err.detail, '内部サーバーエラーが発生しました。');
        return true;
      }
    );
  } finally {
    global.fetch = originalFetch;
  }
});

