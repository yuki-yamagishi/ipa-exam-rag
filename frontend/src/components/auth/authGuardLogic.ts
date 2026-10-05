import type { AuthStatusResponse } from '../../types';

export type AuthGuardStateStatus =
  | 'loading'
  | 'error_fail_closed'
  | 'blocked_unauthenticated'
  | 'authorized';

export interface AuthGuardState {
  status: AuthGuardStateStatus;
  shouldRenderChildren: boolean;
  shouldShowLoginButton: boolean;
  canRetry?: boolean;
  errorMessage?: string;
}

export interface EvaluateAuthGuardInput {
  isLoading: boolean;
  error: string | null;
  authStatus: AuthStatusResponse | null;
}

/**
 * Pure evaluation function for AuthGuard state transitions.
 * Guarantees Fail-Closed principle: If in doubt, loading, or error, block protected content.
 */
export function evaluateAuthGuardState({
  isLoading,
  error,
  authStatus,
}: EvaluateAuthGuardInput): AuthGuardState {
  if (isLoading) {
    return {
      status: 'loading',
      shouldRenderChildren: false,
      shouldShowLoginButton: false,
    };
  }

  if (error) {
    return {
      status: 'error_fail_closed',
      shouldRenderChildren: false,
      shouldShowLoginButton: false,
      canRetry: true,
      errorMessage: error,
    };
  }

  // 疑わしきは遮断 (Fail-Closed): authStatus が null/undefined の場合は未確定としてブロック
  if (!authStatus) {
    return {
      status: 'loading',
      shouldRenderChildren: false,
      shouldShowLoginButton: false,
    };
  }

  // 明示的な許可条件 (Default Deny):
  // 1. 認証機能が無効化されている（ローカル開発環境）
  // 2. 認証が有効であり、かつ正規にログイン済みである
  if (
    authStatus.auth_enabled === false ||
    (authStatus.auth_enabled === true && authStatus.authenticated === true)
  ) {
    return {
      status: 'authorized',
      shouldRenderChildren: true,
      shouldShowLoginButton: false,
    };
  }

  // 上記以外はすべて未認証アクセスとして物理遮断
  return {
    status: 'blocked_unauthenticated',
    shouldRenderChildren: false,
    shouldShowLoginButton: true,
  };
}
