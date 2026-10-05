import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  BookMarked,
  Search,
  Tag,
  X,
  RefreshCw,
  AlertCircle,
  Brain,
  MessageSquare,
} from 'lucide-react';
import { ragApi } from '../api/client';
import type { LearnedInsight } from '../types';
import { InsightCard } from '../components/insights/InsightCard';
import { InsightDetailModal } from '../components/insights/InsightDetailModal';

interface InsightsScreenProps {
  onNavigateToChat?: () => void;
}

export const InsightsScreen: React.FC<InsightsScreenProps> = ({
  onNavigateToChat,
}) => {
  const [insights, setInsights] = useState<LearnedInsight[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [activeModalInsight, setActiveModalInsight] = useState<LearnedInsight | null>(null);

  // 1. Fetch Insights from API
  const fetchInsights = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await ragApi.getInsights(100);
      setInsights(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`ナレッジの読み込みに失敗しました: ${msg}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  // 2. Extract unique tags
  const allUniqueTags = useMemo(() => {
    const tagSet = new Set<string>();
    for (const item of insights) {
      if (item.tags && Array.isArray(item.tags)) {
        for (const tag of item.tags) {
          if (tag.trim()) {
            tagSet.add(tag.trim());
          }
        }
      }
    }
    return Array.from(tagSet).sort();
  }, [insights]);

  // 3. Filtered Insights by Search Query and Selected Tag
  const filteredInsights = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();

    return insights.filter((item) => {
      // Tag filter
      if (selectedTag && (!item.tags || !item.tags.includes(selectedTag))) {
        return false;
      }

      // Keyword query filter
      if (q) {
        const titleMatch = item.title?.toLowerCase().includes(q);
        const conceptMatch = item.core_concept?.toLowerCase().includes(q);
        const trapMatch = item.trap_analysis?.toLowerCase().includes(q);
        const takeawayMatch = item.practical_takeaway?.toLowerCase().includes(q);
        const qidMatch = item.source_question_id?.toLowerCase().includes(q);
        const tagMatch = item.tags?.some((t) => t.toLowerCase().includes(q));

        if (
          !titleMatch &&
          !conceptMatch &&
          !trapMatch &&
          !takeawayMatch &&
          !qidMatch &&
          !tagMatch
        ) {
          return false;
        }
      }

      return true;
    });
  }, [insights, searchQuery, selectedTag]);

  return (
    <div className="space-y-4 pb-12">
      {/* Screen Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <BookMarked className="w-5 h-5 text-emerald-400" />
            <span>ナレッジ</span>
          </h2>
          <p className="text-xs text-slate-400">
            AIとの対話から蓄積された学習ナレッジ
          </p>
        </div>

        <button
          type="button"
          onClick={fetchInsights}
          disabled={isLoading}
          className="p-2 text-slate-400 hover:text-white rounded-xl bg-slate-800 border border-slate-700 hover:border-slate-600 transition min-w-[40px] min-h-[40px] flex items-center justify-center disabled:opacity-50"
          aria-label="ナレッジ一覧を更新"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Search Bar & Tag Filter Controls */}
      <div className="space-y-2.5">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="タイトル、核心概念、設問IDで検索..."
            className="w-full bg-slate-800/90 border border-slate-700/80 rounded-xl pl-10 pr-9 py-2.5 text-xs sm:text-sm text-white placeholder-slate-400 focus:outline-none focus:border-emerald-500 transition min-h-[44px]"
            aria-label="知見をキーワード検索"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 min-w-[36px] min-h-[36px] flex items-center justify-center text-slate-400 hover:text-white transition"
              aria-label="検索キーワードをクリア"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Tag Filter Pills */}
        {allUniqueTags.length > 0 && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-thin">
            <button
              type="button"
              onClick={() => setSelectedTag(null)}
              className={`shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border transition min-h-[30px] ${
                selectedTag === null
                  ? 'bg-emerald-600 text-white border-emerald-500'
                  : 'bg-slate-800 text-slate-300 border-slate-700 hover:border-slate-600'
              }`}
            >
              <span>すべて</span>
              <span className="text-[10px] opacity-75">({insights.length})</span>
            </button>

            {allUniqueTags.map((tag) => {
              const isSelected = selectedTag === tag;
              const count = insights.filter((i) => i.tags?.includes(tag)).length;
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => setSelectedTag(isSelected ? null : tag)}
                  className={`shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border transition min-h-[30px] ${
                    isSelected
                      ? 'bg-emerald-600 text-white border-emerald-500 shadow-sm'
                      : 'bg-slate-800/90 text-slate-300 border-slate-700 hover:border-slate-600'
                  }`}
                  aria-pressed={isSelected}
                >
                  <Tag className="w-3 h-3 shrink-0" />
                  <span>#{tag}</span>
                  <span className="text-[10px] opacity-75">({count})</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Active Filter Summary Bar */}
        {(selectedTag || searchQuery) && (
          <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/30 border border-emerald-800/40 text-xs text-emerald-300">
            <div className="flex items-center gap-1.5 overflow-hidden">
              <span className="font-semibold shrink-0">絞り込み中:</span>
              {selectedTag && (
                <span className="bg-emerald-900/60 px-1.5 py-0.5 rounded text-[11px] shrink-0">
                  #{selectedTag}
                </span>
              )}
              {searchQuery && (
                <span className="truncate text-slate-200">"{searchQuery}"</span>
              )}
            </div>

            <button
              type="button"
              onClick={() => {
                setSelectedTag(null);
                setSearchQuery('');
              }}
              className="text-xs text-slate-400 hover:text-white underline shrink-0 min-h-[28px] px-1"
            >
              リセット
            </button>
          </div>
        )}
      </div>

      {/* Error Alert (Scenario 6) */}
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 p-4 rounded-2xl bg-rose-950/60 border border-rose-800/60 text-rose-200 text-xs sm:text-sm"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={fetchInsights}
            className="px-3 py-1.5 bg-rose-900/60 hover:bg-rose-900 text-rose-200 rounded-xl font-medium shrink-0 flex items-center gap-1.5 transition active:scale-95 min-h-[36px]"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>再試行</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton (Scenario 1) */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              className="rounded-2xl border border-slate-700/50 bg-slate-800/50 p-4 space-y-3 animate-pulse"
            >
              <div className="flex justify-between items-center">
                <div className="h-4 w-28 bg-slate-700 rounded-md" />
                <div className="h-4 w-16 bg-slate-700 rounded-md" />
              </div>
              <div className="h-5 w-4/5 bg-slate-700 rounded-md" />
              <div className="h-4 w-full bg-slate-700/60 rounded-md" />
              <div className="h-4 w-2/3 bg-slate-700/60 rounded-md" />
            </div>
          ))}
        </div>
      )}

      {/* Loaded Content */}
      {!isLoading && !error && (
        <>
          {/* Case A: Filtered Results 0 items */}
          {filteredInsights.length === 0 && insights.length > 0 && (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-8 text-center space-y-3">
              <Search className="w-8 h-8 text-slate-500 mx-auto" />
              <p className="text-sm font-medium text-slate-300">
                条件に一致するナレッジが見つかりませんでした
              </p>
              <p className="text-xs text-slate-400">
                検索キーワードまたはタグのフィルターを変更してお試しください。
              </p>
              <button
                type="button"
                onClick={() => {
                  setSelectedTag(null);
                  setSearchQuery('');
                }}
                className="mt-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-medium transition min-h-[36px]"
              >
                フィルターを全解除
              </button>
            </div>
          )}

          {/* Case B: Total Insights 0 items (Scenario 5 - Empty State) */}
          {insights.length === 0 && (
            <div className="rounded-3xl border border-dashed border-slate-700/80 bg-slate-900/40 p-8 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-emerald-950/60 border border-emerald-800/50 text-emerald-400 flex items-center justify-center mx-auto shadow-inner">
                <Brain className="w-6 h-6" />
              </div>
              <div className="space-y-1.5 max-w-sm mx-auto">
                <h3 className="text-sm font-bold text-white">
                  まだ蓄積されたナレッジがありません
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  過去問の演習や「💡 AI に質問」画面での対話中に、「ナレッジに保存」した解説がここに蓄積されます。
                </p>
              </div>

              {onNavigateToChat && (
                <button
                  type="button"
                  onClick={onNavigateToChat}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow-lg shadow-emerald-900/30 active:scale-95 min-h-[44px]"
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>AI に質問してナレッジを蓄積する</span>
                </button>
              )}
            </div>
          )}

          {/* Case C: Has Insights (Grid List) */}
          {filteredInsights.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {filteredInsights.map((insight) => (
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  onClick={(target) => setActiveModalInsight(target)}
                  onSelectTag={(tag) => setSelectedTag(tag)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* 3-Axis Detail Modal (Scenario 4) */}
      <InsightDetailModal
        insight={activeModalInsight}
        onClose={() => setActiveModalInsight(null)}
        onSelectTag={(tag) => setSelectedTag(tag)}
      />
    </div>
  );
};
