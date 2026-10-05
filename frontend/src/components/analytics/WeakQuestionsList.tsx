import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Flame, XCircle } from 'lucide-react';
import type { WeakQuestionStat } from '../../types';

interface WeakQuestionsListProps {
  weakQuestions: WeakQuestionStat[];
  onNavigateToPractice?: () => void;
}

export const WeakQuestionsList: React.FC<WeakQuestionsListProps> = ({
  weakQuestions,
  onNavigateToPractice,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!weakQuestions || weakQuestions.length === 0) return null;

  return (
    <div className="rounded-3xl border border-slate-700/80 bg-slate-900/90 p-5 shadow-xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Flame className="w-4 h-4 text-rose-400 shrink-0" />
          <h3 className="text-sm font-bold text-white">要復習・弱点問題ランキング</h3>
        </div>
        <span className="text-[11px] text-slate-400">誤答頻出順</span>
      </div>

      {/* Weak Question Cards */}
      <div className="space-y-2.5">
        {weakQuestions.map((q, idx) => {
          const isExpanded = expandedId === q.question_id;

          return (
            <div
              key={q.question_id}
              className="rounded-2xl border border-slate-800/90 bg-slate-800/50 hover:bg-slate-800 transition overflow-hidden"
            >
              {/* Question Row Header */}
              <div
                role="button"
                tabIndex={0}
                onClick={() => setExpandedId(isExpanded ? null : q.question_id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setExpandedId(isExpanded ? null : q.question_id);
                  }
                }}
                className="flex items-center justify-between gap-3 p-3.5 cursor-pointer select-none"
                aria-expanded={isExpanded}
              >
                <div className="flex items-center gap-2.5 flex-1 min-w-0">
                  {/* Rank Badge */}
                  <span className="w-5 h-5 rounded-full bg-rose-950/80 border border-rose-800/80 text-rose-300 text-[11px] font-black flex items-center justify-center shrink-0">
                    {idx + 1}
                  </span>

                  <div className="flex items-center gap-2 flex-wrap min-w-0">
                    <span className="text-xs font-bold text-white shrink-0">
                      問{q.question_number}
                    </span>
                    <span className="text-[11px] px-2 py-0.5 rounded bg-slate-700/60 text-slate-300 truncate max-w-[140px] sm:max-w-xs">
                      {q.category}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 shrink-0 text-xs">
                  {/* Error Count */}
                  <span className="inline-flex items-center gap-1 font-bold text-rose-400">
                    <XCircle className="w-3.5 h-3.5 text-rose-400" />
                    <span>誤答 {q.incorrect_count}回</span>
                  </span>

                  {/* Latest status */}
                  <span
                    className={`inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded font-medium ${
                      q.latest_is_correct
                        ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40'
                        : 'bg-rose-950/60 text-rose-400 border border-rose-800/40'
                    }`}
                  >
                    直近: {q.latest_is_correct ? '正解' : '不正解'}
                  </span>

                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </div>
              </div>

              {/* Expanded Question Details */}
              {isExpanded && (
                <div className="p-3.5 pt-0 border-t border-slate-700/40 space-y-3 text-xs bg-slate-900/40">
                  <p className="text-slate-300 leading-relaxed whitespace-pre-wrap">
                    {q.question_text}
                  </p>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-slate-400">
                      設問ID: {q.question_id}（累計 {q.total_attempts}回挑戦）
                    </span>

                    {onNavigateToPractice && (
                      <button
                        type="button"
                        onClick={onNavigateToPractice}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition text-xs flex items-center gap-1 min-h-[32px] active:scale-95"
                      >
                        道場で再挑戦
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
