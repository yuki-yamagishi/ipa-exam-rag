import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Sparkles, X, AlertCircle, RefreshCw, BookmarkPlus, Check, Loader2, ArrowLeft, BookOpen } from 'lucide-react';
import type { ExamQuestion, RetrievalChunk } from '../../types';
import { ragApi, ApiError } from '../../api/client';
import { CitationCard } from '../chat/CitationCard';
import { MarkdownRenderer } from '../common/MarkdownRenderer';

export interface DojoChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: RetrievalChunk[];
  isStreaming?: boolean;
  isSaved?: boolean;
  error?: string;
}

interface DojoQuestionChatModalProps {
  question: ExamQuestion;
  onClose: () => void;
}

export const DojoQuestionChatModal: React.FC<DojoQuestionChatModalProps> = ({
  question,
  onClose,
}) => {
  const [messages, setMessages] = useState<DojoChatMessage[]>(() => [
    {
      id: 'welcome',
      role: 'assistant',
      content: `【${question.year}年 ${question.term} 問${question.question_number}】について、疑問点や選択肢の正誤理由を何でも質問してください。Qdrant に蓄積された過去問とナレッジを根拠にリアルタイムで解説します。`,
    },
  ]);

  const [inputMessage, setInputMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Clean up streaming and toast timers on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (toastTimerRef.current) {
        clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  // Handle ESC key to close modal safely
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // 1. Send Message and Stream Tokens via SSE
  const handleSendMessage = useCallback(async (retryText?: string, targetAssistantId?: string) => {
    const textToSend = retryText ?? inputMessage;
    const trimmed = textToSend.trim();
    if (!trimmed || isStreaming) return;

    let assistantMsgId: string;

    if (targetAssistantId) {
      assistantMsgId = targetAssistantId;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === targetAssistantId
            ? { ...m, content: '', isStreaming: true, error: undefined, citations: [] }
            : m
        )
      );
    } else {
      const userMsgId = `user-${Date.now()}`;
      assistantMsgId = `assistant-${Date.now()}`;

      const userMsg: DojoChatMessage = {
        id: userMsgId,
        role: 'user',
        content: trimmed,
      };

      const assistantMsg: DojoChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        isStreaming: true,
        citations: [],
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setInputMessage('');
    }

    let historyCandidate = messages.filter(
      (m) => m.id !== 'welcome' && !m.error && m.id !== targetAssistantId
    );
    if (targetAssistantId) {
      const targetIdx = messages.findIndex((m) => m.id === targetAssistantId);
      const prevUserIdx = messages
        .slice(0, targetIdx)
        .map((m, idx) => ({ role: m.role, idx }))
        .reverse()
        .find((m) => m.role === 'user')?.idx;
      if (prevUserIdx !== undefined) {
        const retriedUserMsgId = messages[prevUserIdx].id;
        historyCandidate = historyCandidate.filter((m) => m.id !== retriedUserMsgId);
      }
    }
    const historyPayload = historyCandidate.map((m) => ({ role: m.role, content: m.content }));

    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await ragApi.chatStream(
        {
          question_id: question.id,
          user_message: trimmed,
          dialogue_history: historyPayload,
        },
        {
          onCitation: (chunks) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, citations: chunks } : m
              )
            );
          },
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + token }
                  : m
              )
            );
          },
          onDone: () => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, isStreaming: false } : m
              )
            );
            setIsStreaming(false);
          },
          onError: (err) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      isStreaming: false,
                      error: err.detail || 'AI 回答の生成中にエラーが発生しました',
                    }
                  : m
              )
            );
            setIsStreaming(false);
          },
        },
        controller.signal
      );
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : '通信エラーが発生しました';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? { ...m, isStreaming: false, error: detail }
            : m
        )
      );
      setIsStreaming(false);
    }
  }, [inputMessage, isStreaming, messages, question.id]);

  // 2. Save Knowledge Candidate in Background
  const handleSaveKnowledge = useCallback((msgId: string) => {
    const targetMsg = messages.find((m) => m.id === msgId);
    if (!targetMsg || targetMsg.isSaved) return;

    const targetIdx = messages.findIndex((m) => m.id === msgId);
    const history = messages
      .slice(0, targetIdx + 1)
      .filter((m) => m.id !== 'welcome' && !m.error)
      .map((m) => ({ role: m.role, content: m.content }));

    if (history.length === 0) return;

    ragApi
      .saveKnowledgeCandidate({
        question_id: question.id,
        dialogue_history: history,
      })
      .catch((err) => {
        console.warn('Failed to dispatch background knowledge save:', err);
      });

    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, isSaved: true } : m))
    );

    setToastMessage('💡 ナレッジに保存しました');
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  }, [messages, question.id]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="dojo-chat-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in"
    >
      {/* Toast Notification */}
      {toastMessage && (
        <div
          role="status"
          className="fixed top-5 left-1/2 -translate-x-1/2 z-[60] max-w-[90%] px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-semibold shadow-xl border border-emerald-400/40 flex items-center gap-2 animate-bounceIn"
        >
          <Sparkles className="w-4 h-4 text-emerald-200 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Modal Container */}
      <div className="bg-slate-900 border border-slate-750 rounded-2xl w-full max-w-2xl h-[90vh] max-h-[750px] flex flex-col shadow-2xl overflow-hidden relative">
        {/* Modal Header */}
        <div className="p-4 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              type="button"
              onClick={onClose}
              className="text-slate-400 hover:text-white p-1.5 -ml-1 rounded-lg min-w-[36px] min-h-[36px] flex items-center justify-center transition sm:hidden"
              aria-label="演習に戻る"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="min-w-0">
              <h3 id="dojo-chat-modal-title" className="text-sm font-bold text-white truncate">
                AIに質問 (演習サポート)
              </h3>
              <p className="text-[11px] text-emerald-400 font-medium truncate">
                {question.year}年 {question.term} 問{question.question_number} ({question.category})
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-xl hover:bg-slate-800 transition min-w-[44px] min-h-[44px] flex items-center justify-center shrink-0"
            aria-label="閉じて演習に戻る"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Compact Question Context Strip */}
        <div className="bg-slate-950/60 border-b border-slate-800/80 px-4 py-2.5 shrink-0 flex items-start gap-2.5 text-xs text-slate-300">
          <BookOpen className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <p className="line-clamp-2 leading-relaxed text-slate-300">
            {question.question_text}
          </p>
        </div>

        {/* Chat Messages Scroll Container */}
        <div className="flex-1 overflow-y-auto space-y-3 p-4 no-scrollbar">
          {messages.map((msg) => {
            const isUser = msg.role === 'user';
            return (
              <div
                key={msg.id}
                className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1.5`}
              >
                <div
                  className={`min-w-0 max-w-[92%] sm:max-w-[85%] break-words rounded-2xl p-3.5 text-xs sm:text-sm leading-relaxed shadow-md ${
                    isUser
                      ? 'bg-emerald-600 text-white rounded-br-sm'
                      : 'bg-slate-800/95 border border-slate-700/70 text-slate-100 rounded-bl-sm space-y-2.5'
                  }`}
                >
                  {!isUser && (
                    <div className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-semibold border-b border-slate-700/50 pb-1.5">
                      <Sparkles className="w-3 h-3" />
                      <span>AI解説</span>
                    </div>
                  )}

                  {isUser ? (
                    <div className="whitespace-pre-wrap select-text">
                      {msg.content}
                    </div>
                  ) : (
                    <MarkdownRenderer
                      content={msg.content}
                      isStreaming={msg.isStreaming}
                    />
                  )}

                  {msg.error && (
                    <div
                      role="alert"
                      className="flex items-center gap-2 p-2.5 rounded-xl bg-rose-950/60 border border-rose-800/60 text-rose-200 text-xs mt-2"
                    >
                      <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                      <span className="flex-1">{msg.error}</span>
                      <button
                        type="button"
                        disabled={isStreaming}
                        onClick={() => {
                          const currentIdx = messages.findIndex((m) => m.id === msg.id);
                          const prevUserMsg = messages
                            .slice(0, currentIdx)
                            .reverse()
                            .find((m) => m.role === 'user');
                          if (prevUserMsg) {
                            handleSendMessage(prevUserMsg.content, msg.id);
                          }
                        }}
                        className="px-2.5 py-1 rounded-lg bg-rose-900/60 hover:bg-rose-900 text-rose-200 font-medium shrink-0 flex items-center gap-1 min-h-[32px] cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>再試行</span>
                      </button>
                    </div>
                  )}

                  {!isUser && msg.citations && msg.citations.length > 0 && (
                    <CitationCard citations={msg.citations} />
                  )}

                  {!isUser && !msg.isStreaming && !msg.error && msg.id !== 'welcome' && (
                    <div className="flex items-center justify-end pt-2 border-t border-slate-700/50">
                      <button
                        type="button"
                        onClick={() => handleSaveKnowledge(msg.id)}
                        disabled={msg.isSaved}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium transition min-h-[32px] ${
                          msg.isSaved
                            ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
                            : 'bg-slate-700/60 hover:bg-slate-700 text-slate-300 border border-slate-600/50 active:scale-95'
                        }`}
                        aria-label="この回答をナレッジに保存"
                      >
                        {msg.isSaved ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                            <span>保存済み</span>
                          </>
                        ) : (
                          <>
                            <BookmarkPlus className="w-3.5 h-3.5 text-emerald-300" />
                            <span>💡 ナレッジに保存</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Modal Bottom Input Bar & Navigation Footer */}
        <div className="p-3 sm:p-4 bg-slate-900 border-t border-slate-800 shrink-0 space-y-2.5">
          <div className="relative flex items-center">
            <input
              type="text"
              autoFocus
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder="選択肢の正誤理由や技術概念について質問..."
              disabled={isStreaming}
              className="w-full pl-4 pr-12 py-3 bg-slate-950/90 border border-slate-700/80 rounded-xl text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition disabled:opacity-50"
              aria-label="質問メッセージ入力"
            />
            <button
              type="button"
              onClick={() => handleSendMessage()}
              disabled={!inputMessage.trim() || isStreaming}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 transition min-w-[36px] min-h-[36px] flex items-center justify-center cursor-pointer shadow-md"
              aria-label="質問を送信"
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin text-white" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>

          <div className="flex items-center justify-between gap-3 pt-1">
            <span className="text-[11px] text-slate-400 hidden sm:inline">
              質問後も演習の途中結果・解説はそのまま保持されます
            </span>
            <button
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto px-4 py-2 bg-slate-800 hover:bg-slate-750 border border-slate-700 text-slate-200 hover:text-white rounded-xl text-xs font-semibold transition active:scale-[0.98] min-h-[40px] flex items-center justify-center gap-1.5 shadow-sm"
              aria-label="演習画面に戻る"
            >
              <span>演習に戻る</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
