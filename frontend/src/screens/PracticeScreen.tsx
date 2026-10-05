import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Swords, Play, RefreshCw, AlertCircle, SlidersHorizontal, Loader2 } from 'lucide-react';
import type { AnswerKey, DojoSessionConfig, DojoSessionState, ExamQuestion, PracticeSubmitResponse } from '../types';
import { practiceApi, ApiError } from '../api/client';
import { ResumeBanner } from '../components/practice/ResumeBanner';
import { PracticeConfigModal } from '../components/practice/PracticeConfigModal';
import { QuestionCard } from '../components/practice/QuestionCard';
import { ChoiceList } from '../components/practice/ChoiceList';
import { ExplanationCard } from '../components/practice/ExplanationCard';
import { ResultSummary } from '../components/practice/ResultSummary';
import { DojoQuestionChatModal } from '../components/practice/DojoQuestionChatModal';

export const PracticeScreen: React.FC = () => {
  // Session / Execution states
  const [activeSession, setActiveSession] = useState<DojoSessionState | null>(null);
  const [questions, setQuestions] = useState<ExamQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [currentResult, setCurrentResult] = useState<PracticeSubmitResponse | null>(null);
  const [selectedChoiceKey, setSelectedChoiceKey] = useState<AnswerKey | null>(null);

  // Result accumulation
  const [correctCount, setCorrectCount] = useState<number>(0);
  const [resultsHistory, setResultsHistory] = useState<Array<Record<string, unknown>>>([]);

  // UI state
  const [isConfigModalOpen, setIsConfigModalOpen] = useState<boolean>(false);
  const [isChatModalOpen, setIsChatModalOpen] = useState<boolean>(false);
  const [chatModalQuestion, setChatModalQuestion] = useState<ExamQuestion | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isLoadingNext, setIsLoadingNext] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);

  // Question display start time for accurate time_spent_seconds measurement
  const questionStartTimeRef = useRef<number>(Date.now());

  // 1. Initial Check for Active Resumable Session
  const checkActiveSession = useCallback(async () => {
    try {
      setErrorMessage(null);
      const data = await practiceApi.getActiveSession();
      if (data.session && data.questions && data.questions.length > 0) {
        setActiveSession(data.session);
        setQuestions(data.questions);
      } else {
        setActiveSession(null);
        setQuestions([]);
      }
    } catch (err) {
      console.warn('Failed to check active session:', err);
      // Non-blocking on initial load, but save message if network totally dead
      if (err instanceof ApiError && err.status === 0) {
        setErrorMessage('サーバーまたはネットワークに接続できません。バックエンドが起動しているか確認してください。');
      }
    }
  }, []);

  useEffect(() => {
    checkActiveSession();
  }, [checkActiveSession]);

  // 2. Start a New Practice Session from Config Modal
  const handleStartNewSession = async (config: DojoSessionConfig) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await practiceApi.createSession(config);
      setActiveSession(data.session);
      setQuestions(data.questions);
      setCurrentIndex(0);
      setCurrentResult(null);
      setSelectedChoiceKey(null);
      setCorrectCount(0);
      setResultsHistory([]);
      setIsCompleted(false);
      setIsConfigModalOpen(false);
      questionStartTimeRef.current = Date.now(); // Start timer when session begins
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'セッションの作成に失敗しました';
      setErrorMessage(detail);
    } finally {
      setIsLoading(false);
    }
  };

  // 3. Resume Active Session
  const handleResumeSession = () => {
    if (!activeSession || questions.length === 0) return;
    const resumeIdx = Math.min(activeSession.current_index, questions.length - 1);
    setCurrentIndex(resumeIdx);
    setCurrentResult(null);
    setSelectedChoiceKey(null);
    setIsCompleted(false);
    questionStartTimeRef.current = Date.now(); // Start timer when resuming
  };

  // 4. Discard Active Session
  const handleDiscardSession = async () => {
    if (!activeSession) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await practiceApi.abandonSession(activeSession.session_id);
      setActiveSession(null);
      setQuestions([]);
      setCurrentIndex(0);
      setCurrentResult(null);
      setSelectedChoiceKey(null);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'セッションの破棄に失敗しました';
      setErrorMessage(detail);
    } finally {
      setIsLoading(false);
    }
  };

  // 5. Submit Answer
  const handleSelectChoice = async (key: AnswerKey) => {
    if (isSubmitting || currentResult !== null) return; // Prevent double submission (Scenario 3)
    const currentQ = questions[currentIndex];
    if (!currentQ) return;

    setSelectedChoiceKey(key);
    setIsSubmitting(true);
    setErrorMessage(null);
    const elapsedSeconds = Math.round((Date.now() - questionStartTimeRef.current) / 1000);

    try {
      const resp = await practiceApi.submitAnswer({
        question_id: currentQ.id,
        choice_key: key,
        session_id: activeSession?.session_id || null,
        time_spent_seconds: elapsedSeconds,
      });

      setCurrentResult(resp);
      if (resp.is_correct) {
        setCorrectCount((prev) => prev + 1);
      }
      setResultsHistory((prev) => [
        ...prev,
        {
          question_id: resp.question_id,
          user_choice: resp.user_choice,
          correct_answer: resp.correct_answer,
          is_correct: resp.is_correct,
        },
      ]);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : '解答の送信に失敗しました';
      setErrorMessage(detail);
      setSelectedChoiceKey(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 6. Advance to Next Question or Complete
  const handleNextQuestion = async () => {
    const isLast = currentIndex >= questions.length - 1;

    if (isLast) {
      // Complete Session
      if (activeSession) {
        setIsLoadingNext(true);
        try {
          await practiceApi.completeSession(activeSession.session_id);
        } catch (err) {
          console.warn('Failed to record session completion:', err);
        } finally {
          setIsLoadingNext(false);
        }
      }
      setIsCompleted(true);
      return;
    }

    // Save Progress and go to next question
    const nextIdx = currentIndex + 1;
    if (activeSession) {
      setIsLoadingNext(true);
      try {
        await practiceApi.updateProgress(activeSession.session_id, nextIdx, resultsHistory);
      } catch (err) {
        console.warn('Progress auto-save failed:', err);
      } finally {
        setIsLoadingNext(false);
      }
    }

    setCurrentIndex(nextIdx);
    setCurrentResult(null);
    setSelectedChoiceKey(null);
    questionStartTimeRef.current = Date.now(); // Reset timer for next question
  };

  // 7. Reset / Return to Dojo Home
  const handleResetToHome = () => {
    setActiveSession(null);
    setQuestions([]);
    setCurrentIndex(0);
    setCurrentResult(null);
    setSelectedChoiceKey(null);
    setCorrectCount(0);
    setResultsHistory([]);
    setIsCompleted(false);
    setErrorMessage(null);
    checkActiveSession();
  };

  const handleAskAiQuestion = (question: ExamQuestion) => {
    setChatModalQuestion(question);
    setIsChatModalOpen(true);
  };

  const handleCloseChatModal = () => {
    setIsChatModalOpen(false);
    setChatModalQuestion(null);
  };

  const isInSession = questions.length > 0 && !isCompleted;
  const currentQuestion = isInSession ? questions[currentIndex] : null;

  return (
    <div className="space-y-4 max-w-2xl mx-auto animate-fade-in">
      {/* Error Alert Box (Scenario 9) */}
      {errorMessage && (
        <div
          role="alert"
          className="p-4 bg-rose-950/80 border border-rose-500/60 rounded-2xl text-rose-200 text-xs sm:text-sm flex items-start justify-between gap-3 shadow-md"
        >
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="text-rose-400 hover:text-white p-1 rounded min-w-[36px] min-h-[36px] flex items-center justify-center"
            aria-label="エラーメッセージを閉じる"
          >
            ✕
          </button>
        </div>
      )}

      {/* View 1: Result Summary Screen */}
      {isCompleted && (
        <ResultSummary
          correctCount={correctCount}
          totalCount={questions.length}
          onRetry={() => setIsConfigModalOpen(true)}
          onHome={handleResetToHome}
        />
      )}

      {/* View 2: Active Session Question / Practice */}
      {isInSession && currentQuestion && (
        <div>
          <QuestionCard
            question={currentQuestion}
            currentIndex={currentIndex}
            totalCount={questions.length}
          />

          <ChoiceList
            choices={currentQuestion.choices}
            onSelect={handleSelectChoice}
            result={currentResult}
            selectedKey={selectedChoiceKey}
            isSubmitting={isSubmitting}
          />

          {currentResult && (
            <ExplanationCard
              question={currentQuestion}
              result={currentResult}
              isLastQuestion={currentIndex >= questions.length - 1}
              onNext={handleNextQuestion}
              onAskAi={handleAskAiQuestion}
              isLoadingNext={isLoadingNext}
            />
          )}
        </div>
      )}

      {/* View 3: Idle / Dojo Home View */}
      {!isInSession && !isCompleted && (
        <div className="space-y-4">
          {/* Resume Banner if uncompleted session exists (Scenario 1) */}
          {activeSession && (
            <ResumeBanner
              session={activeSession}
              onResume={handleResumeSession}
              onDiscard={handleDiscardSession}
              isLoading={isLoading}
            />
          )}

          {/* Dojo Start Hero Card */}
          <div className="bg-slate-800/80 border border-slate-700/60 rounded-2xl p-5 sm:p-6 shadow-lg">
            <div className="flex items-center space-x-3 mb-3">
              <div className="w-11 h-11 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                <Swords className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg sm:text-xl font-black text-white">過去問道場</h2>
                <p className="text-xs text-slate-400">高度情報処理 午前II 過去問特訓・即時判定</p>
              </div>
            </div>

            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed mb-5">
              過去問から分野別・ランダムに出題します。
            </p>

            <div className="space-y-2.5">
              <button
                type="button"
                onClick={() => setIsConfigModalOpen(true)}
                disabled={isLoading}
                className="w-full min-h-[52px] bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl shadow-lg flex items-center justify-center gap-2 active:scale-[0.98] transition disabled:opacity-50"
                aria-label="出題設定を開いて演習を開始"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Play className="w-5 h-5 fill-current" />
                    <span>演習を開始する</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => setIsConfigModalOpen(true)}
                className="w-full min-h-[48px] bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white font-medium rounded-xl border border-slate-700/70 flex items-center justify-center gap-2 transition"
              >
                <SlidersHorizontal className="w-4 h-4 text-emerald-400" />
                <span>出題条件をカスタマイズ</span>
              </button>
            </div>
          </div>

          {/* Info Card */}
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-4 text-xs text-slate-400 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <RefreshCw className="w-4 h-4 text-emerald-500" />
              <span>セッション自動保存・中断再開対応</span>
            </span>
            <span className="text-emerald-400/80 font-mono font-semibold">125問 収録</span>
          </div>
        </div>
      )}

      {/* Config Modal */}
      <PracticeConfigModal
        isOpen={isConfigModalOpen}
        onClose={() => setIsConfigModalOpen(false)}
        onStart={handleStartNewSession}
        isLoading={isLoading}
      />

      {/* Dojo In-line Question AI Chat Modal */}
      {isChatModalOpen && chatModalQuestion && (
        <DojoQuestionChatModal
          question={chatModalQuestion}
          onClose={handleCloseChatModal}
        />
      )}
    </div>
  );
};
