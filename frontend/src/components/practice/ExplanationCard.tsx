import React from 'react';
import { CheckCircle2, XCircle, Sparkles, ArrowRight, BookOpen } from 'lucide-react';
import type { ExamQuestion, PracticeSubmitResponse } from '../../types';

interface ExplanationCardProps {
  question: ExamQuestion;
  result: PracticeSubmitResponse;
  isLastQuestion: boolean;
  onNext: () => void;
  onAskAi: (question: ExamQuestion) => void;
  isLoadingNext?: boolean;
}

export const ExplanationCard: React.FC<ExplanationCardProps> = ({
  question,
  result,
  isLastQuestion,
  onNext,
  onAskAi,
  isLoadingNext = false,
}) => {
  const isCorrect = result.is_correct;

  return (
    <div className="mt-5 space-y-4 animate-fade-in">
      {/* Result Status Banner */}
      <div
        className={`p-4 rounded-2xl border flex items-center gap-3 shadow-md ${
          isCorrect
            ? 'bg-emerald-950/80 border-emerald-500/60 text-emerald-300'
            : 'bg-rose-950/80 border-rose-500/60 text-rose-300'
        }`}
      >
        {isCorrect ? (
          <CheckCircle2 className="w-7 h-7 text-emerald-400 flex-shrink-0" />
        ) : (
          <XCircle className="w-7 h-7 text-rose-400 flex-shrink-0" />
        )}
        <div>
          <h4 className="text-base font-bold text-white">
            {isCorrect ? '正解です' : '不正解です'}
          </h4>
          <p className="text-xs text-slate-300 mt-0.5">
            正解は <span className="font-bold text-emerald-400">【{result.correct_answer}】</span> です。
          </p>
        </div>
      </div>

      {/* Official Explanation Body */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-4 sm:p-5 shadow-md">
        <div className="flex items-center gap-2 pb-2.5 border-b border-slate-750 text-xs font-bold text-slate-300">
          <BookOpen className="w-4 h-4 text-emerald-400" />
          <span>公式・技術解説</span>
        </div>

        <div className="mt-3 text-slate-200 text-sm leading-relaxed whitespace-pre-wrap select-text">
          {question.explanation || '公式解説はありません。'}
        </div>

        {/* AI Handoff Action Button */}
        <div className="mt-4 pt-3 border-t border-slate-750/70">
          <button
            type="button"
            onClick={() => onAskAi(question)}
            className="w-full flex items-center justify-center gap-2 min-h-[48px] px-4 py-2.5 bg-gradient-to-r from-emerald-900/60 to-slate-800 hover:from-emerald-800/70 hover:to-slate-750 border border-emerald-500/40 text-emerald-300 hover:text-white rounded-xl transition active:scale-[0.99] text-xs sm:text-sm font-semibold shadow-sm"
            aria-label="この問題を AI に質問する"
          >
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span>💡 この問題を AI に質問する</span>
          </button>
        </div>
      </div>

      {/* Next Question / Finish Button */}
      <button
        type="button"
        onClick={onNext}
        disabled={isLoadingNext}
        className="w-full flex items-center justify-center gap-2 min-h-[52px] bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition active:scale-[0.98] shadow-lg disabled:opacity-50"
        aria-label={isLastQuestion ? '結果を見る' : '次の問題へ進む'}
      >
        <span>{isLastQuestion ? '結果を見る' : '次の問題へ'}</span>
        <ArrowRight className="w-5 h-5" />
      </button>
    </div>
  );
};
