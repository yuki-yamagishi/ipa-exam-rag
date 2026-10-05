import React, { useState, useEffect, useCallback } from 'react';
import { Layout } from './components/Layout';
import type { TabKey } from './components/BottomNav';
import { PracticeScreen } from './screens/PracticeScreen';
import { QuestionsScreen } from './screens/QuestionsScreen';
import { ChatScreen } from './screens/ChatScreen';
import { InsightsScreen } from './screens/InsightsScreen';
import { AnalyticsScreen } from './screens/AnalyticsScreen';
import { NotFoundScreen } from './screens/NotFoundScreen';
import { SettingsModal } from './components/settings/SettingsModal';
import { AuthGuard } from './components/auth/AuthGuard';
import { authApi } from './api/client';
import type { AuthStatusResponse, ExamQuestion } from './types';

const PATH_TO_TAB: Record<string, TabKey> = {
  '/': 'practice',
  '/practice': 'practice',
  '/questions': 'questions',
  '/chat': 'chat',
  '/insights': 'insights',
  '/analytics': 'analytics',
};

const TAB_TO_PATH: Record<TabKey, string> = {
  practice: '/practice',
  questions: '/questions',
  chat: '/chat',
  insights: '/insights',
  analytics: '/analytics',
};

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabKey>('practice');
  const [isNotFound, setIsNotFound] = useState(false);
  const [authStatus, setAuthStatus] = useState<AuthStatusResponse | null>(null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [chatQuestionContext, setChatQuestionContext] = useState<ExamQuestion | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Synchronize route from window.location.pathname
  const syncRouteFromPath = useCallback(() => {
    const path = window.location.pathname.replace(/\/$/, '') || '/';
    if (path in PATH_TO_TAB) {
      setCurrentTab(PATH_TO_TAB[path]);
      setIsNotFound(false);
    } else {
      setIsNotFound(true);
    }
  }, []);

  // Handle browser back/forward buttons
  useEffect(() => {
    syncRouteFromPath();
    const handlePopState = () => {
      syncRouteFromPath();
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [syncRouteFromPath]);

  // Navigate to tab and update browser history
  const handleSelectTab = (tab: TabKey) => {
    setIsNotFound(false);
    setCurrentTab(tab);
    const targetPath = TAB_TO_PATH[tab];
    if (window.location.pathname !== targetPath) {
      window.history.pushState(null, '', targetPath);
    }
  };

  // Seamless Handoff from Question Browse Screen to AI Chat Tab
  const handleAskAiFromQuestions = (question: ExamQuestion) => {
    setChatQuestionContext(question);
    handleSelectTab('chat');
  };

  // Fetch initial auth status with fail-closed error handling
  const fetchAuthStatus = useCallback(async () => {
    setIsLoadingAuth(true);
    setAuthError(null);
    try {
      const status = await authApi.getStatus();
      setAuthStatus(status);
    } catch (err: unknown) {
      console.error('Failed to fetch auth status:', err);
      setAuthError('認証ステータスの確認に失敗しました。サーバーとの接続を確認してください。');
    } finally {
      setIsLoadingAuth(false);
    }
  }, []);

  useEffect(() => {
    fetchAuthStatus();

    const handleUnauthorized = () => {
      fetchAuthStatus();
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [fetchAuthStatus]);

  const handleOpenSettings = useCallback(() => {
    setIsSettingsOpen(true);
  }, []);

  const handleCloseSettings = useCallback(() => {
    setIsSettingsOpen(false);
  }, []);

  const handleAuthStatusChange = useCallback((status: AuthStatusResponse) => {
    setAuthStatus(status);
  }, []);

  return (
    <AuthGuard
      authStatus={authStatus}
      isLoading={isLoadingAuth}
      error={authError}
      onRetry={fetchAuthStatus}
    >
      <Layout
        currentTab={currentTab}
        onSelectTab={handleSelectTab}
        authStatus={authStatus}
        onOpenSettings={handleOpenSettings}
      >
        {isNotFound ? (
          <NotFoundScreen onGoHome={() => handleSelectTab('practice')} />
        ) : (
          <>
            {currentTab === 'practice' && (
              <PracticeScreen />
            )}
            {currentTab === 'questions' && (
              <QuestionsScreen onAskAi={handleAskAiFromQuestions} />
            )}
            {currentTab === 'chat' && (
              <ChatScreen
                questionContext={chatQuestionContext}
                onClearContext={() => setChatQuestionContext(null)}
              />
            )}
            {currentTab === 'insights' && (
              <InsightsScreen onNavigateToChat={() => handleSelectTab('chat')} />
            )}
            {currentTab === 'analytics' && (
              <AnalyticsScreen onNavigateToPractice={() => handleSelectTab('practice')} />
            )}
          </>
        )}
      </Layout>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={handleCloseSettings}
        currentAuthStatus={authStatus}
        onAuthStatusChange={handleAuthStatusChange}
      />
    </AuthGuard>
  );
};

export default App;
