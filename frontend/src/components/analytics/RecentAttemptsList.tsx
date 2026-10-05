import React from 'react';
import { History, CheckCircle2, XCircle, Clock } from 'lucide-react';
import type { PracticeAttempt } from '../../types';

interface RecentAttemptsListProps {
  attempts: PracticeAttempt[];
}

export const RecentAttemptsList: React.FC<RecentAttemptsListProps> = ({ attempts }) => {
  if (!attempts || attempts.length === 0) return null;

  return (
    <div className="rounded-3xl border border-slate-700/80 bg-slate-900/90 p-5 shadow-xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-emerald-400 shrink-0" />
          <h3 className="text-sm font-bold text-white">直近の解答ログ</h3>
        </div>
        <span className="text-[11px] text-slate-400">直近 {attempts.length} 件</span>
      </div>

      {/* Attempts List */}
      <div className="space-y-2">
        {attempts.map((att) => {
          const formattedDate = att.answered_at
            ? new Date(att.answered_at).toLocaleDateString('ja-JP', {
                month: 'numeric',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })
            : '';

          return (
            <div
              key={att.id}
              className="flex items-center justify-between gap-3 p-3 rounded-2xl border border-slate-800/80 bg-slate-800/40 hover:bg-slate-800/70 transition text-xs"
            >
              {/* Left: Result icon & Question identifier */}
              <div className="flex items-center gap-2.5 flex-1 min-w-0">
                {att.is_correct ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                )}

                <div className="min-w-0 space-y-0.5">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-bold text-white">
                      {att.year}年 {att.term} 問{att.question_number}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/60 text-slate-300 truncate max-w-[120px] sm:max-w-xs">
                      {att.category}
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-400">
                    選択: <span className="font-bold text-slate-200">{att.user_choice}</span>
                    {!att.is_correct && (
                      <span className="ml-1 text-rose-300">
                        (正解: <span className="font-bold">{att.correct_answer}</span>)
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Right: Time & Date */}
              <div className="text-right shrink-0 space-y-0.5 text-[11px]">
                <div className="flex items-center justify-end gap-1 text-slate-300 font-medium">
                  <Clock className="w-3 h-3 text-slate-400" />
                  <span>{att.time_spent_seconds}秒</span>
                </div>
                {formattedDate && (
                  <div className="text-[10px] text-slate-400">{formattedDate}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
