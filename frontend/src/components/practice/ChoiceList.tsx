import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import type { AnswerKey, ExamChoice, PracticeSubmitResponse } from '../../types';

interface ChoiceListProps {
  choices: ExamChoice[];
  onSelect: (key: AnswerKey) => void;
  result: PracticeSubmitResponse | null;
  selectedKey: AnswerKey | null;
  isSubmitting?: boolean;
}

export const ChoiceList: React.FC<ChoiceListProps> = ({
  choices,
  onSelect,
  result,
  selectedKey,
  isSubmitting = false,
}) => {
  const isAnswered = result !== null;

  return (
    <div className="space-y-3 mt-4">
      {choices.map((choice) => {
        const isUserChoice = selectedKey === choice.key;
        const isCorrectChoice = result ? result.correct_answer === choice.key : false;
        const isWrongChoice = isUserChoice && result && !result.is_correct;

        // Styling state
        let containerStyle = 'bg-slate-800/70 border-slate-700/70 hover:bg-slate-750 hover:border-slate-600 text-slate-200';
        let keyBadgeStyle = 'bg-slate-700 text-slate-300 border-slate-600';

        if (isAnswered) {
          if (isCorrectChoice) {
            containerStyle = 'bg-emerald-950/80 border-emerald-500 text-white shadow-md ring-1 ring-emerald-500';
            keyBadgeStyle = 'bg-emerald-600 text-white border-emerald-400 font-bold';
          } else if (isWrongChoice) {
            containerStyle = 'bg-rose-950/80 border-rose-500 text-white shadow-md ring-1 ring-rose-500';
            keyBadgeStyle = 'bg-rose-600 text-white border-rose-400 font-bold';
          } else {
            containerStyle = 'bg-slate-850/50 border-slate-800 text-slate-500 opacity-60';
            keyBadgeStyle = 'bg-slate-800 text-slate-500 border-slate-750';
          }
        }

        return (
          <button
            key={choice.key}
            type="button"
            disabled={isAnswered || isSubmitting}
            onClick={() => onSelect(choice.key)}
            className={`w-full text-left p-3.5 sm:p-4 rounded-2xl border transition-all flex items-start gap-3 min-h-[56px] active:scale-[0.99] focus:outline-none ${containerStyle} ${
              isAnswered ? 'pointer-events-none cursor-default' : 'cursor-pointer'
            }`}
            aria-label={`選択肢 ${choice.key}: ${choice.text}`}
          >
            {/* Key Badge */}
            <span
              className={`flex-shrink-0 w-8 h-8 rounded-xl border flex items-center justify-center text-sm font-bold transition-colors mt-0.5 ${keyBadgeStyle}`}
            >
              {choice.key}
            </span>

            {/* Text */}
            <span className="flex-1 text-sm sm:text-base leading-snug pt-1 select-text">
              {choice.text}
            </span>

            {/* Status Icon when Answered */}
            {isAnswered && (
              <span className="flex-shrink-0 pt-1">
                {isCorrectChoice && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
                {isWrongChoice && <XCircle className="w-5 h-5 text-rose-400" />}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
