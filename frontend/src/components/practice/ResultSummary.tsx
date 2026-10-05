import React from 'react';
import { Award, RotateCcw, Home, CheckCircle2 } from 'lucide-react';

interface ResultSummaryProps {
  correctCount: number;
  totalCount: number;
  onRetry: () => void;
  onHome: () => void;
}

export const ResultSummary: React.FC<ResultSummaryProps> = ({
  correctCount,
  totalCount,
  onRetry,
  onHome,
}) => {
  const accuracyRate = totalCount > 0 ? Math.round((correctCount / totalCount) * 100) : 0;
  const isPassed = accuracyRate >= 60;

  return (
    <div className="space-y-5 animate-fade-in text-center max-w-md mx-auto py-4">
      {/* Trophy / Status Icon */}
      <div className="flex justify-center">
        <div
          className={`w-20 h-20 rounded-3xl flex items-center justify-center shadow-xl border ${
            isPassed
              ? 'bg-emerald-950/80 border-emerald-500 text-emerald-400'
              : 'bg-amber-950/80 border-amber-500 text-amber-400'
          }`}
        >
          {isPassed ? <Award className="w-10 h-10" /> : <CheckCircle2 className="w-10 h-10" />}
        </div>
      </div>

      <div>
        <h2 className="text-xl sm:text-2xl font-black text-white">演習セッション完了！</h2>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          {isPassed ? '🎉 合格基準（60%）を達成しました！' : '💪 もう一歩！復習して合格ラインを目指しましょう'}
        </p>
      </div>

      {/* Score Card */}
      <div className="bg-slate-800/90 border border-slate-700/80 rounded-2xl p-6 shadow-md grid grid-cols-2 gap-4">
        <div className="border-r border-slate-750 pr-4">
          <span className="text-xs text-slate-400 font-medium">正解数</span>
          <div className="mt-1 text-2xl sm:text-3xl font-black text-white">
            <span className="text-emerald-400">{correctCount}</span>
            <span className="text-sm text-slate-500 font-normal"> / {totalCount} 問</span>
          </div>
        </div>

        <div className="pl-4">
          <span className="text-xs text-slate-400 font-medium">正解率</span>
          <div className="mt-1 text-2xl sm:text-3xl font-black text-white">
            <span className={isPassed ? 'text-emerald-400' : 'text-amber-400'}>{accuracyRate}%</span>
          </div>
        </div>
      </div>

      {/* Pass/Fail Criteria Indicator */}
      <div className="text-xs text-slate-400 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        高度午前II 試験 合格基準: <strong className="text-slate-200 font-bold">60%以上（15問 / 25問）</strong>
      </div>

      {/* Action Buttons */}
      <div className="pt-2 space-y-2.5">
        <button
          type="button"
          onClick={onRetry}
          className="w-full flex items-center justify-center gap-2 min-h-[52px] bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition active:scale-[0.98] shadow-lg"
          aria-label="新しい演習を開始する"
        >
          <RotateCcw className="w-5 h-5" />
          <span>新しい演習を開始する</span>
        </button>

        <button
          type="button"
          onClick={onHome}
          className="w-full flex items-center justify-center gap-2 min-h-[48px] bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white font-semibold rounded-xl border border-slate-700 transition"
          aria-label="道場トップへ戻る"
        >
          <Home className="w-5 h-5" />
          <span>道場トップへ戻る</span>
        </button>
      </div>
    </div>
  );
};
