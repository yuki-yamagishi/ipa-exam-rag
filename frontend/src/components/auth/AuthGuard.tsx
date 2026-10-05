import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, Loader2, AlertCircle } from 'lucide-react';
import { authApi } from '../../api/client';
import type { AuthStatusResponse } from '../../types';
import { evaluateAuthGuardState } from './authGuardLogic';

export interface AuthGuardProps {
  authStatus: AuthStatusResponse | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  children: React.ReactNode;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({
  authStatus,
  isLoading,
  error,
  onRetry,
  children,
}) => {
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const guardState = evaluateAuthGuardState({ isLoading, error, authStatus });

  const handleLogin = async () => {
    setIsRedirecting(true);
    setLoginError(null);
    try {
      const data = await authApi.getLoginUrl();
      if (data && data.login_url) {
        window.location.href = data.login_url;
      } else {
        throw new Error('ログイン URL の取得に失敗しました。');
      }
    } catch (err: unknown) {
      setIsRedirecting(false);
      const msg = err instanceof Error ? err.message : 'Google ログインの開始に失敗しました。';
      setLoginError(msg);
    }
  };

  // 1. Initializing / Loading Screen
  if (guardState.status === 'loading') {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="w-10 h-10 text-emerald-400 animate-spin" />
          <p className="text-slate-300 text-sm font-medium animate-pulse">
            認証状態を確認中...
          </p>
        </div>
      </div>
    );
  }

  // 2. Fail-Closed Error Screen
  if (guardState.status === 'error_fail_closed') {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-rose-800/60 rounded-2xl p-6 text-center shadow-xl space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-950/60 border border-rose-800 flex items-center justify-center mx-auto text-rose-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">システム接続エラー</h2>
            <p className="text-sm text-slate-400 mt-1">
              {guardState.errorMessage || '認証ステータスの確認に失敗しました。'}
            </p>
          </div>
          <div className="pt-2">
            <button
              type="button"
              onClick={onRetry}
              className="w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-xl border border-slate-700 transition active:scale-95"
            >
              再試行する
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 3. Blocked Unauthenticated - Fullscreen Auth Gate
  if (guardState.status === 'blocked_unauthenticated') {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="text-center space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-emerald-950/60 border border-emerald-800/80 flex items-center justify-center mx-auto text-emerald-400 shadow-inner">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <div>
              <span className="inline-block text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 mb-2">
                AUTHENTICATION REQUIRED
              </span>
              <h1 className="text-xl font-bold tracking-tight text-white">
                IPA Exam RAG ログイン
              </h1>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                本システムは情報処理技術者試験（高度区分/午前II）対策の学習システムです。アクセスには事前に利用許可された Google アカウントでのログインが必要です。
              </p>
            </div>
          </div>

          {loginError && (
            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 flex items-start gap-2.5 text-left text-xs text-rose-300">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{loginError}</span>
            </div>
          )}

          <div className="space-y-3 pt-2">
            <button
              type="button"
              onClick={handleLogin}
              disabled={isRedirecting}
              className="w-full min-h-[50px] flex items-center justify-center gap-3 px-5 py-3 rounded-xl bg-white hover:bg-slate-100 text-slate-900 font-semibold text-sm shadow-md transition active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
            >
              {isRedirecting ? (
                <>
                  <Loader2 className="w-4 h-4 text-slate-900 animate-spin" />
                  <span>Google へ接続中...</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    />
                  </svg>
                  <span>Google アカウントでログイン</span>
                </>
              )}
            </button>

            <p className="text-[11px] text-center text-slate-500 leading-relaxed px-2">
              ※ 事前に登録・許可されていない Google アカウントではログインできません。
            </p>
          </div>
        </div>
      </div>
    );
  }

  // 4. Authorized - Render Application
  return <>{children}</>;
};
