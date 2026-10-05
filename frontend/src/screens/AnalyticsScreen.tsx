import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  RefreshCw,
  AlertCircle,
  GraduationCap,
  PlayCircle,
} from 'lucide-react';
import { analyticsApi } from '../api/client';
import type {
  OverallStat,
  CategoryStat,
  WeakQuestionStat,
  PracticeAttempt,
} from '../types';
import { OverallSummaryCard } from '../components/analytics/OverallSummaryCard';
import { CategoryProgressList } from '../components/analytics/CategoryProgressList';
import { WeakQuestionsList } from '../components/analytics/WeakQuestionsList';
import { RecentAttemptsList } from '../components/analytics/RecentAttemptsList';

interface AnalyticsScreenProps {
  onNavigateToPractice?: () => void;
}

export const AnalyticsScreen: React.FC<AnalyticsScreenProps> = ({
  onNavigateToPractice,
}) => {
  const [summary, setSummary] = useState<OverallStat | null>(null);
  const [categories, setCategories] = useState<CategoryStat[]>([]);
  const [weakQuestions, setWeakQuestions] = useState<WeakQuestionStat[]>([]);
  const [recentAttempts, setRecentAttempts] = useState<PracticeAttempt[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch all analytics data concurrently via Promise.all (Scenario 1, 2, 3, 4, 6)
  const fetchAnalytics = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [sumData, catData, weakData, histData] = await Promise.all([
        analyticsApi.getSummary(),
        analyticsApi.getCategories(),
        analyticsApi.getWeakQuestions(10),
        analyticsApi.getRecentAttempts(20),
      ]);

      setSummary(sumData);
      setCategories(catData);
      setWeakQuestions(weakData);
      setRecentAttempts(histData);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`分析データの取得に失敗しました: ${msg}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const hasHistory = summary && summary.total_attempts > 0;

  return (
    <div className="space-y-5 pb-12">
      {/* Screen Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-400" />
            <span>学習分析 & 弱点</span>
          </h2>
          <p className="text-xs text-slate-400">
            演習履歴・正答率・分野別弱点・頻出誤答ランキング
          </p>
        </div>

        <button
          type="button"
          onClick={fetchAnalytics}
          disabled={isLoading}
          className="p-2 text-slate-400 hover:text-white rounded-xl bg-slate-800 border border-slate-700 hover:border-slate-600 transition min-w-[40px] min-h-[40px] flex items-center justify-center disabled:opacity-50"
          aria-label="分析データを更新"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
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
            onClick={fetchAnalytics}
            className="px-3 py-1.5 bg-rose-900/60 hover:bg-rose-900 text-rose-200 rounded-xl font-medium shrink-0 flex items-center gap-1.5 transition active:scale-95 min-h-[36px]"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>再試行</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-4 animate-pulse">
          <div className="h-36 rounded-3xl bg-slate-800/60 border border-slate-700/50" />
          <div className="h-48 rounded-3xl bg-slate-800/60 border border-slate-700/50" />
          <div className="h-40 rounded-3xl bg-slate-800/60 border border-slate-700/50" />
        </div>
      )}

      {/* Loaded Content */}
      {!isLoading && !error && (
        <>
          {/* Empty State: No Practice History (Scenario 5) */}
          {!hasHistory && (
            <div className="rounded-3xl border border-dashed border-slate-700/80 bg-slate-900/40 p-8 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-emerald-950/60 border border-emerald-800/50 text-emerald-400 flex items-center justify-center mx-auto shadow-inner">
                <GraduationCap className="w-6 h-6" />
              </div>
              <div className="space-y-1.5 max-w-sm mx-auto">
                <h3 className="text-sm font-bold text-white">まだ解答履歴がありません</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  「🥋 過去問道場」で過去問を解くと、正答率、分野ごとの習熟度、要復習問題ランキング、直近の解答ログがここに自動集計されます。
                </p>
              </div>

              {onNavigateToPractice && (
                <button
                  type="button"
                  onClick={onNavigateToPractice}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow-lg shadow-emerald-900/30 active:scale-95 min-h-[44px]"
                >
                  <PlayCircle className="w-4 h-4" />
                  <span>過去問道場で演習を始める</span>
                </button>
              )}
            </div>
          )}

          {/* Has Practice History */}
          {hasHistory && summary && (
            <div className="space-y-5">
              {/* 1. Overall KPI Summary Card (Scenario 1) */}
              <OverallSummaryCard summary={summary} />

              {/* 2. Category Performance Progress Bars & Alerts (Scenario 2) */}
              <CategoryProgressList categories={categories} />

              {/* 3. Weak Questions Ranking List (Scenario 3) */}
              <WeakQuestionsList
                weakQuestions={weakQuestions}
                onNavigateToPractice={onNavigateToPractice}
              />

              {/* 4. Recent Attempts Log Timeline (Scenario 4) */}
              <RecentAttemptsList attempts={recentAttempts} />
            </div>
          )}
        </>
      )}
    </div>
  );
};
