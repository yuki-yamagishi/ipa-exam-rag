import React from 'react';
import { Tag, Calendar, HelpCircle } from 'lucide-react';
import type { ExamQuestion } from '../../types';
import { formatQuestionSource } from '../../utils/attribution';

interface QuestionCardProps {
  question: ExamQuestion;
  currentIndex: number;
  totalCount: number;
}

export const QuestionCard: React.FC<QuestionCardProps> = ({
  question,
  currentIndex,
  totalCount,
}) => {
  return (
    <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-4 sm:p-6 shadow-md transition-all">
      {/* Meta Headers */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-750 text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="px-2.5 py-1 bg-emerald-950/60 text-emerald-400 font-bold rounded-lg border border-emerald-800/50 flex items-center gap-1">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>問 {question.question_number}</span>
          </span>

          <span className="px-2.5 py-1 bg-slate-700/50 text-slate-300 font-medium rounded-lg flex items-center gap-1">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>{question.year}年 {question.term}</span>
          </span>

          <span className="px-2.5 py-1 bg-slate-750 text-slate-300 rounded-lg flex items-center gap-1">
            <Tag className="w-3.5 h-3.5 text-slate-400" />
            <span>{question.category}</span>
          </span>
        </div>

        <div className="text-slate-400 font-mono text-xs">
          進捗: <span className="text-white font-bold">{currentIndex + 1}</span> / {totalCount}
        </div>
      </div>

      {/* Question Text */}
      <div className="mt-4 text-slate-100 text-sm sm:text-base leading-relaxed tracking-wide whitespace-pre-wrap select-text font-normal">
        {question.question_text}
      </div>

      {/* Official IPA Source Attribution */}
      <div className="mt-4 pt-3 border-t border-slate-750/60 text-[11px] text-slate-400 select-text font-normal">
        {formatQuestionSource(question)}
      </div>
    </div>
  );
};
