import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import type { RetrievalChunk } from '../../types';

interface CitationCardProps {
  citations: RetrievalChunk[];
}

export const CitationCard: React.FC<CitationCardProps> = ({ citations }) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);

  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-2.5 rounded-xl border border-slate-700/60 bg-slate-900/70 p-3 text-xs shadow-sm">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between text-left text-slate-300 hover:text-white transition min-h-[36px]"
        aria-expanded={isOpen}
        aria-label="参照したナレッジの展開・折りたたみ"
      >
        <div className="flex items-center gap-1.5 font-semibold text-emerald-400">
          <BookOpen className="w-4 h-4 shrink-0" />
          <span>参照したナレッジ（Citation）</span>
          <span className="ml-1 rounded-full bg-emerald-500/20 px-2 py-0.2 text-[10px] text-emerald-300 font-bold">
            {citations.length} 件
          </span>
        </div>
        {isOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>

      {isOpen && (
        <div className="mt-2.5 space-y-2 border-t border-slate-800/80 pt-2 animate-fadeIn">
          {citations.map((chunk, idx) => {
            const similarityPercent = Math.round((chunk.score || 0) * 100);
            const isInsight = chunk.doc_type === 'learned_insight';
            const isSyllabus = chunk.doc_type === 'syllabus';

            const badgeBg = isInsight
              ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
              : isSyllabus
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
              : 'bg-blue-500/20 text-blue-300 border-blue-500/30';

            const badgeLabel = isInsight
              ? '蓄積知見'
              : isSyllabus
              ? '公式シラバス'
              : '公式過去問';

            const title =
              (chunk.metadata && typeof chunk.metadata.title === 'string' && chunk.metadata.title) ||
              (chunk.metadata && typeof chunk.metadata.question_id === 'string' && chunk.metadata.question_id) ||
              `参照ソース #${idx + 1}`;

            return (
              <div
                key={chunk.id || idx}
                className="rounded-lg border border-slate-800 bg-slate-950/50 p-2.5 space-y-1.5 transition hover:border-slate-700/80"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border shrink-0 ${badgeBg}`}>
                      {badgeLabel}
                    </span>
                    <span className="truncate font-medium text-slate-200 text-xs">
                      {title}
                    </span>
                  </div>
                  {chunk.score > 0 && (
                    <span className="shrink-0 text-[10px] text-emerald-400 font-mono bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
                      関連度 {similarityPercent}%
                    </span>
                  )}
                </div>

                <p className="text-slate-400 text-[11px] leading-relaxed line-clamp-2 select-text pl-1 border-l border-slate-700/60">
                  {chunk.content}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
