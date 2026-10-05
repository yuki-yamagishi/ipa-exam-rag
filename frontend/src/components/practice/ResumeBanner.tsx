import React from 'react';
import { Play, Trash2 } from 'lucide-react';
import type { DojoSessionState } from '../../types';

interface ResumeBannerProps {
  session: DojoSessionState;
  onResume: () => void;
  onDiscard: () => void;
  isLoading?: boolean;
}

export const ResumeBanner: React.FC<ResumeBannerProps> = ({
  session,
  onResume,
  onDiscard,
  isLoading = false,
}) => {
  const currentNum = Math.min(session.current_index + 1, session.question_count);
  const totalNum = session.question_count;

  return (
    <div className="bg-gradient-to-r from-emerald-950/80 to-slate-900 border border-emerald-500/30 rounded-2xl p-4 shadow-lg mb-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <h3 className="text-sm font-semibold text-white">中断中の演習セッションがあります</h3>
          </div>
          <p className="text-xs text-slate-300">
            進捗: <span className="font-bold text-emerald-400">{currentNum}</span> / {totalNum} 問目
            {session.category && ` (${session.category})`}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onResume}
            disabled={isLoading}
            className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl transition min-h-[48px] active:scale-95 shadow-md disabled:opacity-50"
            aria-label="前回のセッションを再開する"
          >
            <Play className="w-4 h-4 fill-white" />
            <span>再開する</span>
          </button>
          <button
            type="button"
            onClick={onDiscard}
            disabled={isLoading}
            className="p-2.5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 rounded-xl transition min-w-[48px] min-h-[48px] flex items-center justify-center border border-slate-700/60 disabled:opacity-50"
            title="セッションを破棄"
            aria-label="中断中のセッションを破棄する"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
