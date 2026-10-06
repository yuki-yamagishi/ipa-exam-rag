import React, { useEffect } from 'react';
import {
  X,
  Sparkles,
  ShieldCheck,
  Target,
  AlertTriangle,
  Briefcase,
  Calendar,
  Tag,
} from 'lucide-react';
import type { LearnedInsight } from '../../types';
import { formatQuestionSourceFromId } from '../../utils/attribution';

interface InsightDetailModalProps {
  insight: LearnedInsight | null;
  onClose: () => void;
  onSelectTag?: (tag: string) => void;
}

export const InsightDetailModal: React.FC<InsightDetailModalProps> = ({
  insight,
  onClose,
  onSelectTag,
}) => {
  // Close on ESC key and prevent background body scroll when open
  useEffect(() => {
    if (!insight) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = originalOverflow;
    };
  }, [insight, onClose]);

  if (!insight) return null;

  const formattedDate = insight.created_at
    ? new Date(insight.created_at).toLocaleDateString('ja-JP', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : '';

  const confidencePercent = Math.round((insight.confidence_score || 0) * 100);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="insight-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg max-h-[88vh] flex flex-col rounded-3xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 p-5 border-b border-slate-800 bg-slate-900/90">
          <div className="space-y-1.5 flex-1 pr-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300 border border-slate-700">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>{formatQuestionSourceFromId(insight.source_question_id)}</span>
              </span>

              {insight.is_verified && (
                <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-950/70 px-2.5 py-1 text-xs font-semibold text-emerald-300 border border-emerald-800/60">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>AI検証済 ({confidencePercent}%)</span>
                </span>
              )}
            </div>

            <h2
              id="insight-modal-title"
              className="text-base sm:text-lg font-bold text-white leading-snug"
            >
              {insight.title}
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 transition min-w-[40px] min-h-[40px] flex items-center justify-center shrink-0"
            aria-label="閉じる"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs sm:text-sm">
          {/* 1. Core Concept */}
          <div className="rounded-2xl border border-emerald-800/50 bg-emerald-950/20 p-4 space-y-2">
            <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-wider">
              <Target className="w-4 h-4 shrink-0" />
              <span>🎯 核心概念 (Core Concept)</span>
            </div>
            <p className="text-slate-200 whitespace-pre-wrap leading-relaxed">
              {insight.core_concept}
            </p>
          </div>

          {/* 2. Trap Analysis */}
          <div className="rounded-2xl border border-amber-800/50 bg-amber-950/20 p-4 space-y-2">
            <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>⚠️ 誤答トラップ (Trap Analysis)</span>
            </div>
            <p className="text-slate-200 whitespace-pre-wrap leading-relaxed">
              {insight.trap_analysis}
            </p>
          </div>

          {/* 3. Practical Takeaway */}
          <div className="rounded-2xl border border-sky-800/50 bg-sky-950/20 p-4 space-y-2">
            <div className="flex items-center gap-2 text-sky-400 font-bold text-xs uppercase tracking-wider">
              <Briefcase className="w-4 h-4 shrink-0" />
              <span>💼 実務・設計指針 (Practical Takeaway)</span>
            </div>
            <p className="text-slate-200 whitespace-pre-wrap leading-relaxed">
              {insight.practical_takeaway}
            </p>
          </div>

          {/* Metadata Section */}
          <div className="pt-2 flex flex-col gap-2.5 text-xs text-slate-400 border-t border-slate-800/80">
            {formattedDate && (
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-slate-500" />
                <span>登録日: {formattedDate}</span>
              </div>
            )}

            {insight.tags && insight.tags.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <Tag className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                <span>タグ:</span>
                {insight.tags.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => {
                      onSelectTag?.(tag);
                      onClose();
                    }}
                    className="inline-flex items-center gap-1 rounded-md bg-slate-800 hover:bg-emerald-950/50 hover:text-emerald-300 hover:border-emerald-800/50 px-2 py-0.5 text-xs text-slate-300 border border-slate-700 transition"
                  >
                    <span>#{tag}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition min-h-[44px] flex items-center justify-center active:scale-95"
          >
            閉じる
          </button>
        </div>
      </div>
    </div>
  );
};
