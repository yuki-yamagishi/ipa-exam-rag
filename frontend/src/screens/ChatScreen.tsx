import React, { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, X, HelpCircle, AlertCircle, RefreshCw, BookmarkPlus, Check, Loader2 } from 'lucide-react';
import type { ExamQuestion, RetrievalChunk } from '../types';
import { ragApi, ApiError } from '../api/client';
import { CitationCard } from '../components/chat/CitationCard';
import { MarkdownRenderer } from '../components/common/MarkdownRenderer';

// Default fallback question ID if no specific question context is passed
const DEFAULT_QUESTION_ID = '2025-SA-AM2-Q01';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: RetrievalChunk[];
  isStreaming?: boolean;
  isSaved?: boolean;
  error?: string;
}

interface ChatScreenProps {
  questionContext?: ExamQuestion | null;
  onClearContext?: () => void;
}

export const ChatScreen: React.FC<ChatScreenProps> = ({
  questionContext,
  onClearContext,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: 'welcome',
      role: 'assistant',
      content: questionContext
        ? `【${questionContext.year}年 ${questionContext.term} 問${questionContext.question_number}】について、疑問点や選択肢の正誤理由を何でも質問してください。Qdrant に蓄積された過去問とナレッジを根拠にリアルタイムで解説します。`
        : 'IPA 高度情報処理技術者試験の過去問や技術概念について何でも質問してください。Qdrant のナレッジベースから公式根拠を参照してリアルタイムで回答します。',
    },
  ]);

  const [inputMessage, setInputMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-scroll on new message or streaming tokens
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

  // Update initial welcome message if questionContext changes
  useEffect(() => {
    if (questionContext && messages.length === 1 && messages[0].id === 'welcome') {
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content: `【${questionContext.year}年 ${questionContext.term} 問${questionContext.question_number}】について、疑問点や選択肢の正誤理由を何でも質問してください。Qdrant に蓄積された過去問とナレッジを根拠にリアルタイムで解説します。`,
        },
      ]);
    }
  }, [questionContext, messages.length, messages[0]?.id]);

  // 1. Send Message and Stream Tokens via SSE (Scenarios 1, 2, 5, 6)
  const handleSendMessage = async (retryText?: string, targetAssistantId?: string) => {
    const textToSend = retryText ?? inputMessage;
    const trimmed = textToSend.trim();
    if (!trimmed || isStreaming) return; // Prevent empty or double submissions (Scenario 6)

    const targetQuestionId = questionContext?.id || DEFAULT_QUESTION_ID;
    let assistantMsgId: string;

    if (targetAssistantId) {
      assistantMsgId = targetAssistantId;
      // Reset failed assistant message to streaming state
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

      // 1. Append user message and empty streaming assistant bubble
      const userMsg: ChatMessage = {
        id: userMsgId,
        role: 'user',
        content: trimmed,
      };

      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        isStreaming: true,
        citations: [],
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setInputMessage('');
    }

    // Construct dialogue history for API (exclude welcome, active target bubble, and the retried user message itself)
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
          question_id: targetQuestionId,
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
  };

  // 2. Save Knowledge Candidate in Background (Scenario 4)
  const handleSaveKnowledge = (msgId: string) => {
    const targetMsg = messages.find((m) => m.id === msgId);
    if (!targetMsg || targetMsg.isSaved) return;

    // Collect dialogue history up to this message
    const targetIdx = messages.findIndex((m) => m.id === msgId);
    const history = messages
      .slice(0, targetIdx + 1)
      .filter((m) => m.id !== 'welcome' && !m.error)
      .map((m) => ({ role: m.role, content: m.content }));

    if (history.length === 0) return;

    const targetQuestionId = questionContext?.id || DEFAULT_QUESTION_ID;

    // Fire-and-forget in background without blocking UI
    ragApi
      .saveKnowledgeCandidate({
        question_id: targetQuestionId,
        dialogue_history: history,
      })
      .catch((err) => {
        console.warn('Failed to dispatch background knowledge save:', err);
      });

    // Mark as saved and show immediate non-blocking toast
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, isSaved: true } : m))
    );

    setToastMessage('💡 ナレッジに保存しました');
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] relative">
      {/* Toast Notification */}
      {toastMessage && (
        <div
          role="status"
          className="absolute top-2 left-1/2 -translate-x-1/2 z-50 max-w-[90%] px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-semibold shadow-xl border border-emerald-400/40 flex items-center gap-2 animate-bounceIn"
        >
          <Sparkles className="w-4 h-4 text-emerald-200 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Chat Messages Scroll Container */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4 px-1 no-scrollbar">
        {/* Context Handoff Banner from Dojo Practice (Scenario 3) */}
        {questionContext && (
          <div className="bg-gradient-to-r from-emerald-950/80 to-slate-900 border border-emerald-500/40 rounded-2xl p-3.5 shadow-md flex items-start justify-between gap-3 animate-fadeIn">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-400">
                <HelpCircle className="w-4 h-4 shrink-0" />
                <span>対象設問: {questionContext.year}年 {questionContext.term} 問{questionContext.question_number}</span>
              </div>
              <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                {questionContext.question_text}
              </p>
            </div>
            {onClearContext && (
              <button
                type="button"
                onClick={onClearContext}
                className="text-slate-400 hover:text-white p-1 rounded-lg min-w-[36px] min-h-[36px] flex items-center justify-center shrink-0 transition"
                title="コンテキストを解除"
                aria-label="設問コンテキストを解除"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        )}

        {/* Messages List */}
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1.5`}
            >
              {/* Message Bubble */}
              <div
                className={`min-w-0 max-w-[90%] md:max-w-[80%] break-words rounded-2xl p-4 text-sm leading-relaxed shadow-md ${
                  isUser
                    ? 'bg-emerald-600 text-white rounded-br-sm'
                    : 'bg-slate-800/90 border border-slate-700/70 text-slate-100 rounded-bl-sm space-y-3'
                }`}
              >
                {!isUser && (
                  <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-semibold border-b border-slate-700/50 pb-2">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>AI</span>
                  </div>
                )}

                {/* Message Content */}
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

                {/* Error Banner inside Bubble (Scenario 5) */}
                {msg.error && (
                  <div
                    role="alert"
                    className="flex items-center gap-2 p-3 rounded-xl bg-rose-950/60 border border-rose-800/60 text-rose-200 text-xs mt-2"
                  >
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span className="flex-1">{msg.error}</span>
                    <button
                      type="button"
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
                      className="px-2.5 py-1 rounded-lg bg-rose-900/60 hover:bg-rose-900 text-rose-200 font-medium shrink-0 flex items-center gap-1 min-h-[32px] cursor-pointer"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>再試行</span>
                    </button>
                  </div>
                )}

                {/* Grounding Citation Cards (Scenario 2) */}
                {!isUser && msg.citations && msg.citations.length > 0 && (
                  <CitationCard citations={msg.citations} />
                )}

                {/* Save Knowledge Action Button (Scenario 4) */}
                {!isUser && !msg.isStreaming && !msg.error && msg.id !== 'welcome' && (
                  <div className="flex items-center justify-end pt-2 border-t border-slate-700/50">
                    <button
                      type="button"
                      onClick={() => handleSaveKnowledge(msg.id)}
                      disabled={msg.isSaved}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition min-h-[36px] ${
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

      {/* Fixed Bottom Input Bar (Thumb-zone optimized) */}
      <div className="sticky bottom-0 pt-2 bg-[#0B0F19]">
        <div className="relative flex items-center">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            placeholder={
              questionContext
                ? `問${questionContext.question_number} について AI に質問...`
                : 'AI に質問を入力...'
            }
            disabled={isStreaming}
            className="w-full min-h-[52px] bg-slate-800 border border-slate-700 rounded-2xl pl-4 pr-14 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-emerald-500 transition shadow-inner disabled:opacity-50"
            aria-label="AI への質問入力"
          />
          <button
            type="button"
            onClick={() => handleSendMessage()}
            disabled={isStreaming || !inputMessage.trim()}
            className="absolute right-1 p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl min-w-[44px] min-h-[44px] flex items-center justify-center transition active:scale-95 shadow-md disabled:opacity-40 disabled:pointer-events-none"
            aria-label="質問を送信"
          >
            {isStreaming ? (
              <Loader2 className="w-5 h-5 animate-spin text-emerald-200" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
