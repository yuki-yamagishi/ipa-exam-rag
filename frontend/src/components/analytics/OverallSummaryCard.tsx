import React from 'react';
import { Award, Target, CheckCircle2, BookOpen, Layers } from 'lucide-react';
import type { OverallStat } from '../../types';

interface OverallSummaryCardProps {
  summary: OverallStat;
}

export const OverallSummaryCard: React.FC<OverallSummaryCardProps> = ({ summary }) => {
  const accuracyPercent = Math.round((summary.accuracy_rate || 0) * 100);
  const isPassing = accuracyPercent >= 60;

  return (
    <div className="rounded-3xl border border-slate-700/80 bg-slate-900/90 p-5 shadow-xl space-y-4">
      {/* Header with Main Accuracy Metric */}
      <div className="flex items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium">
            <Award className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>総合正答率</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className={`text-3xl sm:text-4xl font-black tracking-tight ${
                isPassing ? 'text-emerald-400' : 'text-amber-400'
              }`}
            >
              {accuracyPercent}%
            </span>
            <span className="text-xs text-slate-400">
              (基準: 60% / {isPassing ? '合格圏内 🎯' : '要対策 ⚠️'})
            </span>
          </div>
        </div>

        <div
          className={`px-3 py-1.5 rounded-xl border text-xs font-bold shrink-0 ${
            isPassing
              ? 'bg-emerald-950/60 border-emerald-800/60 text-emerald-300'
              : 'bg-amber-950/60 border-amber-800/60 text-amber-300'
          }`}
        >
          {isPassing ? '合格水準クリア' : '合格水準まであと少し'}
        </div>
      </div>

      {/* 4 KPI Grid Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {/* KPI 1: 総解答数 */}
        <div className="rounded-2xl border border-slate-800/80 bg-slate-800/60 p-3 space-y-1">
          <div className="flex items-center gap-1 text-[11px] text-slate-400">
            <Target className="w-3.5 h-3.5 text-slate-400" />
            <span>総解答数</span>
          </div>
          <p className="text-lg sm:text-xl font-bold text-white">
            {summary.total_attempts} <span className="text-xs text-slate-400 font-normal">問</span>
          </p>
        </div>

        {/* KPI 2: 正解数 */}
        <div className="rounded-2xl border border-slate-800/80 bg-slate-800/60 p-3 space-y-1">
          <div className="flex items-center gap-1 text-[11px] text-slate-400">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>正解数</span>
          </div>
          <p className="text-lg sm:text-xl font-bold text-emerald-400">
            {summary.correct_attempts} <span className="text-xs text-slate-400 font-normal">問</span>
          </p>
        </div>

        {/* KPI 3: 挑戦設問数 */}
        <div className="rounded-2xl border border-slate-800/80 bg-slate-800/60 p-3 space-y-1">
          <div className="flex items-center gap-1 text-[11px] text-slate-400">
            <BookOpen className="w-3.5 h-3.5 text-sky-400" />
            <span>挑戦設問</span>
          </div>
          <p className="text-lg sm:text-xl font-bold text-white">
            {summary.distinct_questions_attempted} <span className="text-xs text-slate-400 font-normal">/ 125</span>
          </p>
        </div>

        {/* KPI 4: 完了セッション */}
        <div className="rounded-2xl border border-slate-800/80 bg-slate-800/60 p-3 space-y-1">
          <div className="flex items-center gap-1 text-[11px] text-slate-400">
            <Layers className="w-3.5 h-3.5 text-purple-400" />
            <span>演習回数</span>
          </div>
          <p className="text-lg sm:text-xl font-bold text-white">
            {summary.total_sessions} <span className="text-xs text-slate-400 font-normal">回</span>
          </p>
        </div>
      </div>
    </div>
  );
};
