import React, { useState, useEffect, useRef } from 'react';
import { Search, Filter, BookOpen, AlertCircle, RefreshCw, Loader2, X } from 'lucide-react';
import type { ExamQuestion } from '../types';
import { questionsApi, ApiError } from '../api/client';
import { QuestionBrowseCard } from '../components/browse/QuestionBrowseCard';

const PAGE_SIZE = 20;

interface QuestionsScreenProps {
  onAskAi?: (question: ExamQuestion) => void;
}

export const QuestionsScreen: React.FC<QuestionsScreenProps> = ({ onAskAi }) => {
  // Data states
  const [questions, setQuestions] = useState<ExamQuestion[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [years, setYears] = useState<number[]>([]);
  const [categories, setCategories] = useState<string[]>([]);

  // Filter states
  const [searchKeyword, setSearchKeyword] = useState<string>('');
  const [debouncedKeyword, setDebouncedKeyword] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Loading & Error states
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 1. Debounce keyword search input by 500ms
  const handleKeywordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchKeyword(val);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      setDebouncedKeyword(val.trim());
    }, 500);
  };

  const handleClearKeyword = () => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    setSearchKeyword('');
    setDebouncedKeyword('');
  };

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // 2. Fetch master filters (years & categories) on mount
  useEffect(() => {
    let isMounted = true;
    const fetchMasters = async () => {
      try {
        const [yearsData, catsData] = await Promise.all([
          questionsApi.getYears().catch((err) => {
            console.warn('Failed to load years:', err);
            return [] as number[];
          }),
          questionsApi.getCategories().catch((err) => {
            console.warn('Failed to load categories:', err);
            return [] as string[];
          }),
        ]);
        if (isMounted) {
          setYears(yearsData);
          setCategories(catsData);
        }
      } catch (err) {
        console.warn('Failed to fetch filter options:', err);
      }
    };
    fetchMasters();
    return () => {
      isMounted = false;
    };
  }, []);

  // 3. Fetch questions on filter/search change with race condition prevention
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setErrorMessage(null);

    questionsApi
      .getQuestions({
        year: selectedYear ?? undefined,
        category: selectedCategory ?? undefined,
        keyword: debouncedKeyword || undefined,
        limit: PAGE_SIZE,
        offset: 0,
      })
      .then((resp) => {
        if (!active) return;
        setQuestions(resp.items);
        setTotal(resp.total);
      })
      .catch((err) => {
        if (!active) return;
        const detail = err instanceof ApiError ? err.detail : '設問の取得に失敗しました';
        setErrorMessage(detail);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedYear, selectedCategory, debouncedKeyword, refreshTrigger]);

  // 4. Load more questions (pagination)
  const handleLoadMore = async () => {
    if (isLoadingMore || questions.length >= total) return;
    setIsLoadingMore(true);

    try {
      const resp = await questionsApi.getQuestions({
        year: selectedYear ?? undefined,
        category: selectedCategory ?? undefined,
        keyword: debouncedKeyword || undefined,
        limit: PAGE_SIZE,
        offset: questions.length,
      });

      setQuestions((prev) => [...prev, ...resp.items]);
      setTotal(resp.total);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : '追加設問の取得に失敗しました';
      setErrorMessage(detail);
    } finally {
      setIsLoadingMore(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="relative">
        <Search className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        <input
          type="search"
          value={searchKeyword}
          onChange={handleKeywordChange}
          placeholder="キーワードや設問番号で検索..."
          className="w-full min-h-[48px] bg-slate-800/80 border border-slate-700/60 rounded-xl pl-11 pr-10 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition"
          aria-label="過去問検索キーワード"
        />
        {searchKeyword && (
          <button
            type="button"
            onClick={handleClearKeyword}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-white transition"
            aria-label="検索キーワードをクリア"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Filter Badges & Selectors */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs no-scrollbar">
          <div className="flex items-center gap-1.5 shrink-0 text-slate-400 px-1">
            <Filter className="w-3.5 h-3.5 text-emerald-400" />
            <span className="font-medium">絞り込み:</span>
          </div>

          {/* Year Filter */}
          <select
            value={selectedYear ?? ''}
            onChange={(e) => {
              const val = e.target.value ? Number(e.target.value) : null;
              setSelectedYear(val);
            }}
            className="px-3 py-1.5 rounded-lg bg-slate-800/90 text-slate-200 border border-slate-700/70 text-xs font-medium focus:outline-none focus:border-emerald-500 transition"
            aria-label="年度フィルター"
          >
            <option value="">全年度</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}年度
              </option>
            ))}
          </select>

          {/* Category Filter */}
          <select
            value={selectedCategory ?? ''}
            onChange={(e) => {
              const val = e.target.value || null;
              setSelectedCategory(val);
            }}
            className="px-3 py-1.5 rounded-lg bg-slate-800/90 text-slate-200 border border-slate-700/70 text-xs font-medium focus:outline-none focus:border-emerald-500 transition"
            aria-label="分野フィルター"
          >
            <option value="">全分野</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          {/* Active Filter Clear */}
          {(selectedYear !== null || selectedCategory !== null || debouncedKeyword) && (
            <button
              type="button"
              onClick={() => {
                setSelectedYear(null);
                setSelectedCategory(null);
                handleClearKeyword();
              }}
              className="px-2.5 py-1.5 rounded-lg bg-slate-700/60 hover:bg-slate-700 text-slate-300 text-xs font-medium whitespace-nowrap transition"
            >
              条件リセット
            </button>
          )}
        </div>

        {/* Total Summary */}
        <div className="flex items-center justify-between text-xs text-slate-400 px-1">
          <span>
            {isLoading ? (
              '設問を読み込み中...'
            ) : (
              <>
                <strong className="text-emerald-400">{total}</strong> 問中{' '}
                <strong className="text-slate-200">{questions.length}</strong> 問を表示
              </>
            )}
          </span>
          {debouncedKeyword && (
            <span className="text-slate-400 truncate max-w-[200px]">
              キーワード: &ldquo;{debouncedKeyword}&rdquo;
            </span>
          )}
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div
          role="alert"
          className="flex items-start gap-3 p-4 rounded-2xl bg-rose-950/60 border border-rose-800/60 text-rose-200 text-xs md:text-sm animate-fadeIn"
        >
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1">
            <p className="font-semibold text-rose-300">エラーが発生しました</p>
            <p className="text-rose-200/90 leading-relaxed">{errorMessage}</p>
          </div>
          <button
            type="button"
            onClick={() => setRefreshTrigger((prev) => prev + 1)}
            className="px-3 py-1.5 rounded-xl bg-rose-900/60 hover:bg-rose-900 text-rose-200 text-xs font-medium transition shrink-0 flex items-center gap-1"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>再試行</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-slate-800/40 border border-slate-800/60 rounded-2xl p-5 space-y-3 animate-pulse"
            >
              <div className="flex items-center justify-between">
                <div className="h-5 w-24 bg-slate-700/60 rounded" />
                <div className="h-4 w-16 bg-slate-700/40 rounded" />
              </div>
              <div className="h-16 bg-slate-700/30 rounded" />
              <div className="space-y-1.5">
                <div className="h-8 bg-slate-700/20 rounded" />
                <div className="h-8 bg-slate-700/20 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : questions.length === 0 ? (
        /* Empty State */
        <div className="bg-slate-800/40 border border-slate-800/60 rounded-2xl p-8 text-center text-slate-400 space-y-3">
          <BookOpen className="w-10 h-10 text-slate-500 mx-auto" />
          <p className="text-sm font-semibold text-slate-200">一致する設問が見つかりませんでした</p>
          <p className="text-xs text-slate-400">
            検索キーワードや年度・分野の絞り込み条件を変更してお試しください。
          </p>
        </div>
      ) : (
        /* Question Cards List */
        <div className="space-y-4">
          {questions.map((question) => (
            <QuestionBrowseCard key={question.id} question={question} onAskAi={onAskAi} />
          ))}

          {/* Load More Button */}
          {questions.length < total && (
            <div className="pt-2 pb-4 text-center">
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={isLoadingMore}
                className="w-full max-w-sm mx-auto flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-slate-800 hover:bg-slate-700/80 border border-slate-700/70 text-slate-200 text-sm font-medium transition active:scale-95 disabled:opacity-50 min-h-[48px]"
                aria-label="さらに設問を読み込む"
              >
                {isLoadingMore ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                    <span>読み込み中...</span>
                  </>
                ) : (
                  <span>さらに読み込む (残り {total - questions.length} 問)</span>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
