import React from 'react';
import { Sparkles, Tag, ShieldCheck, Calendar, ArrowRight } from 'lucide-react';
import type { LearnedInsight } from '../../types';

interface InsightCardProps {
  insight: LearnedInsight;
  onClick: (insight: LearnedInsight) => void;
  onSelectTag?: (tag: string) => void;
}

export const InsightCard: React.FC<InsightCardProps> = ({
  insight,
  onClick,
  onSelectTag,
}) => {
  const formattedDate = insight.created_at
    ? new Date(insight.created_at).toLocaleDateString('ja-JP', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : '';

  const confidencePercent = Math.round((insight.confidence_score || 0) * 100);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onClick(insight)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick(insight);
        }
      }}
      className="group relative flex flex-col justify-between rounded-2xl border border-slate-700/70 bg-slate-800/90 p-4 transition-all duration-200 hover:border-emerald-500/50 hover:bg-slate-800 hover:shadow-lg hover:shadow-emerald-950/20 active:scale-[0.99] cursor-pointer text-left focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
      aria-label={`知見: ${insight.title}`}
    >
      <div>
        {/* Header Badges */}
        <div className="flex items-center justify-between gap-2 mb-2.5">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="inline-flex items-center gap-1 rounded-lg bg-slate-700/60 px-2 py-0.5 text-[11px] font-medium text-slate-300 border border-slate-600/50">
              <Sparkles className="w-3 h-3 text-emerald-400 shrink-0" />
              <span>{insight.source_question_id}</span>
            </span>

            {insight.is_verified && (
              <span className="inline-flex items-center gap-0.5 rounded-lg bg-emerald-950/60 px-2 py-0.5 text-[11px] font-medium text-emerald-300 border border-emerald-800/50">
                <ShieldCheck className="w-3 h-3 text-emerald-400 shrink-0" />
                <span>AI検証済 ({confidencePercent}%)</span>
              </span>
            )}
          </div>

          {formattedDate && (
            <div className="flex items-center gap-1 text-[11px] text-slate-400 shrink-0">
              <Calendar className="w-3 h-3 text-slate-400" />
              <span>{formattedDate}</span>
            </div>
          )}
        </div>

        {/* Title */}
        <h3 className="text-sm font-bold text-white group-hover:text-emerald-300 transition-colors line-clamp-2 leading-snug">
          {insight.title}
        </h3>

        {/* Core Concept Preview */}
        <p className="mt-2 text-xs text-slate-300 line-clamp-2 leading-relaxed">
          {insight.core_concept}
        </p>
      </div>

      {/* Footer: Tags & Arrow */}
      <div className="mt-3.5 flex items-center justify-between gap-2 pt-2.5 border-t border-slate-700/50">
        <div className="flex items-center gap-1.5 flex-wrap flex-1 overflow-hidden">
          {insight.tags && insight.tags.length > 0 ? (
            insight.tags.slice(0, 3).map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectTag?.(tag);
                }}
                className="inline-flex items-center gap-1 rounded-md bg-slate-900/60 hover:bg-emerald-950/50 hover:text-emerald-300 hover:border-emerald-800/50 px-2 py-0.5 text-[11px] text-slate-400 border border-slate-700/60 transition min-h-[26px]"
                aria-label={`タグで絞り込み: ${tag}`}
              >
                <Tag className="w-2.5 h-2.5 shrink-0" />
                <span>{tag}</span>
              </button>
            ))
          ) : (
            <span className="text-[11px] text-slate-400">#一般知見</span>
          )}
          {insight.tags && insight.tags.length > 3 && (
            <span className="text-[10px] text-slate-400 font-medium">
              +{insight.tags.length - 3}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 text-xs font-medium text-emerald-400 shrink-0 group-hover:translate-x-0.5 transition-transform">
          <span>詳細</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </div>
      </div>
    </div>
  );
};
