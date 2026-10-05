import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  X,
  Key,
  Database,
  Trash2,
  LogIn,
  LogOut,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  ShieldCheck,
  UserCheck,
  Cpu,
} from 'lucide-react';
import { systemApi, authApi, ApiError } from '../../api/client';
import type { SystemSettingsResponse, AuthStatusResponse } from '../../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentAuthStatus?: AuthStatusResponse | null;
  onAuthStatusChange?: (status: AuthStatusResponse) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  currentAuthStatus,
  onAuthStatusChange,
}) => {
  const [settings, setSettings] = useState<SystemSettingsResponse | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatusResponse | null>(currentAuthStatus || null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Sync authStatus when external prop changes
  useEffect(() => {
    if (currentAuthStatus !== undefined) {
      setAuthStatus(currentAuthStatus);
    }
  }, [currentAuthStatus]);

  // Keep latest refs to prevent infinite dependency loop
  const onAuthStatusChangeRef = useRef(onAuthStatusChange);
  useEffect(() => {
    onAuthStatusChangeRef.current = onAuthStatusChange;
  });

  const authStatusRef = useRef(authStatus);
  useEffect(() => {
    authStatusRef.current = authStatus;
  }, [authStatus]);

  // API Key Form State
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showApiKeyText, setShowApiKeyText] = useState(false);
  const [isUpdatingKey, setIsUpdatingKey] = useState(false);

  // Reindex State
  const [isReindexing, setIsReindexing] = useState(false);

  // Reset History State
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  // Auth Action State
  const [isAuthProcessing, setIsAuthProcessing] = useState(false);

  // Fetch settings & auth status on open (stable callback, zero props/state dependency)
  const fetchSettingsAndAuth = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [fetchedSettings, fetchedAuth] = await Promise.all([
        systemApi.getSettings(),
        authApi.getStatus(),
      ]);
      setSettings(fetchedSettings);
      setAuthStatus(fetchedAuth);

      // Only notify parent if authentication status has actually changed
      const prev = authStatusRef.current;
      const isChanged =
        !prev ||
        prev.auth_enabled !== fetchedAuth.auth_enabled ||
        prev.authenticated !== fetchedAuth.authenticated ||
        prev.user_email !== fetchedAuth.user_email;

      if (isChanged && onAuthStatusChangeRef.current) {
        onAuthStatusChangeRef.current(fetchedAuth);
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : '設定情報の取得に失敗しました。';
      setErrorMessage(detail);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchSettingsAndAuth();
      setShowResetConfirm(false);
      setSuccessMessage(null);
      setApiKeyInput('');
    }
  }, [isOpen, fetchSettingsAndAuth]);

  // Body Scroll Lock & ESC Key handler
  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  // Handler: Update API Key
  const handleUpdateApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedKey = apiKeyInput.trim();
    if (!trimmedKey) {
      setErrorMessage('有効な Gemini API キーを入力してください。');
      return;
    }

    setIsUpdatingKey(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await systemApi.updateApiKey(trimmedKey);
      setSuccessMessage(res.message || 'API キーを正常に更新しました。');
      setApiKeyInput('');
      setShowApiKeyText(false);
      if (settings) {
        setSettings({
          ...settings,
          gemini_api_key_masked: res.gemini_api_key_masked,
        });
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'API キーの更新に失敗しました。';
      setErrorMessage(detail);
    } finally {
      setIsUpdatingKey(false);
    }
  };

  // Handler: Reindex Vector Store
  const handleReindex = async () => {
    setIsReindexing(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await systemApi.reindexAll();
      setSuccessMessage(res.message || `${res.reindexed_count} 件の設問を再インデックスしました。`);
      if (settings) {
        setSettings({
          ...settings,
          vector_store_points_count: res.reindexed_count,
        });
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : '再インデックスに失敗しました。';
      setErrorMessage(detail);
    } finally {
      setIsReindexing(false);
    }
  };

  // Handler: Reset Practice History
  const handleResetHistory = async () => {
    setIsResetting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await systemApi.resetHistory();
      setSuccessMessage(res.message || '学習履歴をすべて消去しました。');
      setShowResetConfirm(false);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : '学習履歴のリセットに失敗しました。';
      setErrorMessage(detail);
    } finally {
      setIsResetting(false);
    }
  };

  // Handler: Google OAuth Login
  const handleLogin = async () => {
    setIsAuthProcessing(true);
    setErrorMessage(null);

    try {
      const res = await authApi.getLoginUrl();
      if (res.login_url) {
        window.location.href = res.login_url;
      } else {
        setErrorMessage('ログイン URL の生成に失敗しました。');
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'ログイン処理の呼び出しに失敗しました。';
      setErrorMessage(detail);
    } finally {
      setIsAuthProcessing(false);
    }
  };

  // Handler: Google OAuth Logout
  const handleLogout = async () => {
    setIsAuthProcessing(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await authApi.logout();
      setSuccessMessage(res.message || 'ログアウトしました。');
      const updatedAuth: AuthStatusResponse = {
        auth_enabled: true,
        authenticated: false,
        user_email: null,
      };
      setAuthStatus(updatedAuth);
      if (onAuthStatusChangeRef.current) {
        onAuthStatusChangeRef.current(updatedAuth);
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'ログアウト処理に失敗しました。';
      setErrorMessage(detail);
    } finally {
      setIsAuthProcessing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg rounded-3xl border border-slate-700/80 bg-slate-900 shadow-2xl p-6 text-slate-100 space-y-6 my-auto max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">⚙️</span>
            <div>
              <h2 id="settings-modal-title" className="text-base font-bold text-white">
                システム設定 & アカウント管理
              </h2>
              <p className="text-[11px] text-slate-400">
                API キー、ベクトル検索、学習履歴および認証状態の管理
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-full hover:bg-slate-800 active:scale-95 transition min-w-[44px] min-h-[44px] flex items-center justify-center"
            aria-label="設定モーダルを閉じる"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Global Notifications */}
        {errorMessage && (
          <div role="alert" className="p-3.5 rounded-2xl bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2.5 animate-fadeIn">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span className="flex-1">{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div role="status" className="p-3.5 rounded-2xl bg-emerald-950/50 border border-emerald-800/80 text-emerald-300 text-xs flex items-center gap-2.5 animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="flex-1">{successMessage}</span>
          </div>
        )}

        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-3">
            <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
            <span className="text-xs text-slate-400">システム設定を読み込み中...</span>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Section 1: Gemini API Key */}
            <section className="space-y-3 p-4 rounded-2xl border border-slate-800/80 bg-slate-800/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-bold text-white">
                  <Key className="w-4 h-4 text-amber-400" />
                  <h3>Gemini API キー設定</h3>
                </div>
                {settings?.gemini_api_key_masked && (
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-700/60 text-slate-300 border border-slate-600/50">
                    {settings.gemini_api_key_masked}
                  </span>
                )}
              </div>

              {settings && (
                <div className="text-[11px] text-slate-400 space-y-1">
                  <div className="flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-slate-500" />
                    <span>生成モデル: <strong className="text-slate-200">{settings.gemini_model_generate}</strong></span>
                  </div>
                  {settings.gemini_model_generate_fallback && (
                    <div className="text-slate-500 text-[10px] pl-5">
                      フォールバック: {settings.gemini_model_generate_fallback}
                    </div>
                  )}
                </div>
              )}

              <form onSubmit={handleUpdateApiKey} className="space-y-2 pt-1">
                <div className="relative">
                  <input
                    type={showApiKeyText ? 'text' : 'password'}
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder="新しい Gemini API キーを入力 (AIza...)"
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-400 pr-10 min-h-[44px]"
                    disabled={isUpdatingKey}
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKeyText(!showApiKeyText)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-slate-200 min-w-[36px] min-h-[36px] flex items-center justify-center"
                    aria-label={showApiKeyText ? 'APIキーを伏字にする' : 'APIキーを表示する'}
                  >
                    {showApiKeyText ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={isUpdatingKey || !apiKeyInput.trim()}
                  className="w-full py-2.5 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 active:scale-[0.99] disabled:opacity-40 disabled:pointer-events-none text-slate-950 font-bold text-xs transition flex items-center justify-center gap-1.5 min-h-[44px]"
                >
                  {isUpdatingKey ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>キーを更新中...</span>
                    </>
                  ) : (
                    <span>API キーを更新</span>
                  )}
                </button>
              </form>
            </section>

            {/* Section 2: Qdrant Vector Store */}
            <section className="space-y-3 p-4 rounded-2xl border border-slate-800/80 bg-slate-800/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-bold text-white">
                  <Database className="w-4 h-4 text-emerald-400" />
                  <h3>Qdrant ベクトルストア</h3>
                </div>
                <span className="text-[11px] text-slate-300">
                  格納ポイント: <strong className="text-emerald-400 font-mono">{settings?.vector_store_points_count ?? 0}</strong> 件
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                公式過去問および蓄積されたナレッジのインデックスを再構築します。
              </p>
              <button
                type="button"
                onClick={handleReindex}
                disabled={isReindexing}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 active:scale-[0.99] disabled:opacity-40 disabled:pointer-events-none text-white font-bold text-xs transition flex items-center justify-center gap-1.5 min-h-[44px]"
              >
                {isReindexing ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
                    <span>全問再インデックス中...</span>
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 text-emerald-400" />
                    <span>全 125 問を再インデックス</span>
                  </>
                )}
              </button>
            </section>

            {/* Section 3: Reset Practice History */}
            <section className="space-y-3 p-4 rounded-2xl border border-rose-900/40 bg-rose-950/10">
              <div className="flex items-center gap-2 text-sm font-bold text-rose-300">
                <Trash2 className="w-4 h-4 text-rose-400" />
                <h3>学習履歴・セッションのリセット</h3>
              </div>
              <p className="text-[11px] text-slate-400">
                演習の全解答履歴、学習傾向ダッシュボード集計、および中断セッションを完全に初期化します。
              </p>

              {!showResetConfirm ? (
                <button
                  type="button"
                  onClick={() => setShowResetConfirm(true)}
                  className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-rose-950/40 border border-rose-800/60 active:scale-[0.99] text-rose-300 font-bold text-xs transition flex items-center justify-center gap-1.5 min-h-[44px]"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>学習履歴を初期化する</span>
                </button>
              ) : (
                <div className="p-3.5 rounded-xl border border-rose-800/80 bg-rose-950/40 space-y-3 animate-fadeIn">
                  <div className="flex items-start gap-2 text-xs text-rose-200">
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                    <span>⚠️ この操作は取り消せません。本当にすべての学習履歴を消去しますか？</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowResetConfirm(false)}
                      disabled={isResetting}
                      className="flex-1 py-2.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition min-h-[44px]"
                    >
                      キャンセル
                    </button>
                    <button
                      type="button"
                      onClick={handleResetHistory}
                      disabled={isResetting}
                      className="flex-1 py-2.5 px-3 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition flex items-center justify-center gap-1.5 min-h-[44px]"
                    >
                      {isResetting ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          <span>消去中...</span>
                        </>
                      ) : (
                        <span>完全に消去する</span>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </section>

            {/* Section 4: Account & Auth Management */}
            <section className="space-y-3 p-4 rounded-2xl border border-slate-800/80 bg-slate-800/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-bold text-white">
                  <ShieldCheck className="w-4 h-4 text-cyan-400" />
                  <h3>アカウント & 認証管理</h3>
                </div>
                {authStatus?.auth_enabled === false && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/50">
                    認証OFF (開発モード)
                  </span>
                )}
              </div>

              {authStatus?.auth_enabled === false ? (
                <div className="text-[11px] text-slate-400 p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0" />
                  <span>認証は無効化されています（ローカル開発環境）。ログイン操作は不要です。</span>
                </div>
              ) : authStatus?.authenticated ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/80 border border-slate-700/60">
                    <div className="flex items-center gap-2 min-w-0">
                      <UserCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                      <div className="min-w-0">
                        <div className="text-[10px] text-slate-400">ログイン中アカウント</div>
                        <div className="text-xs font-bold text-white truncate max-w-[200px] sm:max-w-xs">
                          {authStatus.user_email}
                        </div>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleLogout}
                    disabled={isAuthProcessing}
                    className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 active:scale-[0.99] text-rose-300 font-bold text-xs transition flex items-center justify-center gap-1.5 min-h-[44px]"
                  >
                    {isAuthProcessing ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>ログアウト中...</span>
                      </>
                    ) : (
                      <>
                        <LogOut className="w-3.5 h-3.5" />
                        <span>ログアウト</span>
                      </>
                    )}
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-[11px] text-slate-400">
                    本システムのご利用には、認可済み Google アカウントでのログインが必要です。
                  </p>
                  <button
                    type="button"
                    onClick={handleLogin}
                    disabled={isAuthProcessing}
                    className="w-full py-2.5 px-4 rounded-xl bg-white hover:bg-slate-100 text-slate-950 font-bold text-xs transition flex items-center justify-center gap-2 min-h-[44px] shadow-md"
                  >
                    {isAuthProcessing ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin text-slate-950" />
                        <span>認証サーバーへ接続中...</span>
                      </>
                    ) : (
                      <>
                        <LogIn className="w-4 h-4 text-slate-950" />
                        <span>Google アカウントでログイン</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </section>

            {/* 著作権 & 免責事項 */}
            <div className="pt-3 pb-1 border-t border-slate-850 text-[10px] text-slate-500 leading-relaxed text-center space-y-0.5">
              <p>
                収録されている過去試験問題および解答例の著作権は、
                <span className="text-slate-400 font-medium">独立行政法人情報処理推進機構（IPA）</span> に帰属します。
              </p>
              <p className="text-slate-600">
                本システムは開発者個人による学習・技術検証を目的とした非公式ツールです。
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
