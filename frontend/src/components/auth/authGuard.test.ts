import { test } from 'node:test';
import assert from 'node:assert/strict';
import { authApi } from '../../api/client.ts';
import type { AuthStatusResponse } from '../../types/index.ts';
import { evaluateAuthGuardState } from './authGuardLogic.ts';

test('Scenario 1: Unauthenticated user is blocked by AuthGuard', async () => {
  const authStatus: AuthStatusResponse = {
    auth_enabled: true,
    authenticated: false,
    user_email: null,
  };

  const state = evaluateAuthGuardState({
    isLoading: false,
    error: null,
    authStatus,
  });

  assert.equal(state.status, 'blocked_unauthenticated');
  assert.equal(state.shouldRenderChildren, false);
  assert.equal(state.shouldShowLoginButton, true);

  // Verify login URL fetch
  const originalFetch = global.fetch;
  global.fetch = async () => {
    return new Response(
      JSON.stringify({
        login_url: 'https://accounts.google.com/o/oauth2/v2/auth?test=1',
        state: 'csrf-token-123',
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  };

  try {
    const loginData = await authApi.getLoginUrl();
    assert.match(loginData.login_url, /accounts\.google\.com/);
  } finally {
    global.fetch = originalFetch;
  }
});

test('Scenario 2: Authenticated user is permitted by AuthGuard', () => {
  const authStatus: AuthStatusResponse = {
    auth_enabled: true,
    authenticated: true,
    user_email: 'authorized.user@example.com',
  };

  const state = evaluateAuthGuardState({
    isLoading: false,
    error: null,
    authStatus,
  });

  assert.equal(state.status, 'authorized');
  assert.equal(state.shouldRenderChildren, true);
  assert.equal(state.shouldShowLoginButton, false);
});

test('Scenario 3: Loading state shows initialization spinner', () => {
  const state = evaluateAuthGuardState({
    isLoading: true,
    error: null,
    authStatus: null,
  });

  assert.equal(state.status, 'loading');
  assert.equal(state.shouldRenderChildren, false);
});

test('Scenario 4: Auth disabled (local dev) bypasses AuthGuard', () => {
  const authStatus: AuthStatusResponse = {
    auth_enabled: false,
    authenticated: true,
    user_email: null,
  };

  const state = evaluateAuthGuardState({
    isLoading: false,
    error: null,
    authStatus,
  });

  assert.equal(state.status, 'authorized');
  assert.equal(state.shouldRenderChildren, true);
});

test('Scenario 8: Network/Server error strictly fails closed (blocks content and provides retry)', () => {
  const state = evaluateAuthGuardState({
    isLoading: false,
    error: '認証サーバーとの通信に失敗しました。',
    authStatus: null,
  });

  assert.equal(state.status, 'error_fail_closed');
  assert.equal(state.shouldRenderChildren, false);
  assert.equal(state.canRetry, true);
  assert.equal(state.errorMessage, '認証サーバーとの通信に失敗しました。');
});

test('Scenario: null authStatus without loading strictly fails closed (Default Deny)', () => {
  const state = evaluateAuthGuardState({
    isLoading: false,
    error: null,
    authStatus: null,
  });

  assert.notEqual(state.status, 'authorized');
  assert.equal(state.shouldRenderChildren, false);
  assert.equal(state.status, 'loading');
});

