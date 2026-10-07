import React, { useState } from 'react';
import { Sparkles, ChevronDown, ChevronUp, CheckCircle2, BookOpen } from 'lucide-react';
import type { ExamQuestion } from '../../types';
import { formatQuestionSource } from '../../utils/attribution';

interface QuestionBrowseCardProps {
  question: ExamQuestion;
  onAskAi?: (question: ExamQuestion) => void;
}

export const QuestionBrowseCard: React.FC<QuestionBrowseCardProps> = ({ question, onAskAi }) => {
  const [showExplanation, setShowExplanation] = useState<boolean>(false);

  return (
    <article
      className="bg-slate-800/90 border border-slate-700/70 rounded-2xl p-5 shadow-lg transition hover:border-slate-600/80 space-y-4"
      aria-labelledby={`question-title-${question.id}`}
    >
      {/* 1. Header Badges */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700/50 pb-3">
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
            {question.year}年 {question.term}
          </span>
          <span
            id={`question-title-${question.id}`}
            className="px-2.5 py-1 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 text-xs font-bold"
          >
            問 {question.question_number}
          </span>
        </div>
        <span className="px-2.5 py-0.5 rounded-full bg-slate-700/60 text-slate-300 text-xs font-medium">
          {question.category}
        </span>
      </div>

      {/* 2. Question Text */}
      <div className="text-sm md:text-base text-slate-100 leading-relaxed font-normal whitespace-pre-wrap select-text">
        {question.question_text}
      </div>

      {/* 3. Choices Preview */}
      <div className="space-y-1.5 pt-1">
        {question.choices.map((choice) => {
          const isCorrect = showExplanation && choice.key === question.correct_answer;
          return (
            <div
              key={choice.key}
              className={`flex items-start gap-2.5 p-2.5 rounded-xl border text-xs md:text-sm transition ${
                isCorrect
                  ? 'bg-emerald-950/40 border-emerald-600/60 text-emerald-200 font-medium'
                  : 'bg-slate-900/40 border-slate-800/80 text-slate-300'
              }`}
            >
              <span
                className={`w-5 h-5 rounded-md flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 ${
                  isCorrect ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'
                }`}
              >
                {choice.key}
              </span>
              <span className="flex-1 leading-relaxed">{choice.text}</span>
            </div>
          );
        })}
      </div>

      {/* 4. Explanation Section (Collapsible) */}
      {showExplanation && (
        <div className="bg-slate-900/60 border border-emerald-900/40 rounded-xl p-4 text-xs md:text-sm space-y-2 animate-fadeIn">
          <div className="flex items-center gap-1.5 text-emerald-400 font-semibold text-xs">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>正解: 【{question.correct_answer}】</span>
          </div>
          <div className="text-slate-300 leading-relaxed whitespace-pre-wrap select-text pl-1 border-l-2 border-emerald-600/40">
            {question.explanation}
          </div>
        </div>
      )}

      {/* Official IPA Source Attribution */}
      <div className="text-[11px] text-slate-400 select-text font-normal pt-1">
        {formatQuestionSource(question)}
      </div>

      {/* 5. Actions: Explanation Toggle & Ask AI */}
      <div className="flex items-center justify-between gap-3 pt-2 border-t border-slate-700/50">
        <button
          type="button"
          onClick={() => setShowExplanation((prev) => !prev)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-700/60 hover:bg-slate-700 text-slate-300 text-xs font-medium transition min-h-[44px]"
          aria-expanded={showExplanation}
          aria-label={showExplanation ? '解説を閉じる' : '正解と解説を見る'}
        >
          <BookOpen className="w-4 h-4 text-slate-400" />
          <span>{showExplanation ? '解説を閉じる' : '正解・解説を見る'}</span>
          {showExplanation ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {onAskAi && (
          <button
            type="button"
            onClick={() => onAskAi(question)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-950/40 transition active:scale-95 min-h-[44px]"
            aria-label={`問${question.question_number}についてAIに質問する`}
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-200" />
            <span>AI に質問する</span>
          </button>
        )}
      </div>
    </article>
  );
};
