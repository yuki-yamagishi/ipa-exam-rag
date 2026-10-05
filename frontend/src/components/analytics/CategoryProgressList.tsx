import React from 'react';
import { BarChart3, AlertTriangle } from 'lucide-react';
import type { CategoryStat } from '../../types';

interface CategoryProgressListProps {
  categories: CategoryStat[];
}

export const CategoryProgressList: React.FC<CategoryProgressListProps> = ({ categories }) => {
  if (!categories || categories.length === 0) return null;

  return (
    <div className="rounded-3xl border border-slate-700/80 bg-slate-900/90 p-5 shadow-xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-emerald-400 shrink-0" />
          <h3 className="text-sm font-bold text-white">分野別習熟度 & 正答率</h3>
        </div>
        <span className="text-[11px] text-slate-400">合格基準: 60%</span>
      </div>

      {/* Categories Progress Bars */}
      <div className="space-y-4">
        {categories.map((cat) => {
          const percent = Math.round((cat.accuracy_rate || 0) * 100);
          const isPassing = percent >= 60;

          return (
            <div key={cat.category} className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 flex-1 min-w-0 pr-2">
                  <span className="font-semibold text-slate-200 truncate">
                    {cat.category}
                  </span>
                  {!isPassing && (
                    <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold bg-amber-950/80 text-amber-300 border border-amber-800/60 shrink-0">
                      <AlertTriangle className="w-2.5 h-2.5 text-amber-400" />
                      <span>要重点対策</span>
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 text-[11px] shrink-0">
                  <span className="text-slate-400">
                    {cat.correct_attempts}/{cat.total_attempts}問
                  </span>
                  <span
                    className={`font-bold min-w-[36px] text-right ${
                      isPassing ? 'text-emerald-400' : 'text-amber-400'
                    }`}
                  >
                    {percent}%
                  </span>
                </div>
              </div>

              {/* Progress Bar with 60% Passing Line Marker */}
              <div className="relative w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                {/* 60% Goal Line Marker */}
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-slate-500/80 z-10"
                  style={{ left: '60%' }}
                  title="合格基準 60%"
                />
                {/* Active Progress */}
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    isPassing
                      ? 'bg-gradient-to-r from-emerald-600 to-emerald-400'
                      : 'bg-gradient-to-r from-amber-600 to-amber-400'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
