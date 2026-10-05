import React, { useState, useEffect } from 'react';
import { X, Play, SlidersHorizontal, BookOpen, CheckCircle, AlertTriangle, HelpCircle } from 'lucide-react';
import type { DojoMode, DojoSessionConfig } from '../../types';
import { questionsApi } from '../../api/client';

interface PracticeConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStart: (config: DojoSessionConfig) => void;
  isLoading?: boolean;
}

const MODES: Array<{ mode: DojoMode; label: string; desc: string; icon: React.FC<{ className?: string }> }> = [
  { mode: 'all', label: '全問ランダム', desc: '過去問全体からバランスよく出題', icon: BookOpen },
  { mode: 'category', label: '分野別特訓', desc: '特定の出題分野を集中的に演習', icon: CheckCircle },
  { mode: 'weak_incorrect', label: '要復習 (誤答)', desc: '過去に間違えた問題から優先出題', icon: AlertTriangle },
  { mode: 'unanswered', label: '未解答マスター', desc: 'まだ一度も解いていない問題を出題', icon: HelpCircle },
];

export const PracticeConfigModal: React.FC<PracticeConfigModalProps> = ({
  isOpen,
  onClose,
  onStart,
  isLoading = false,
}) => {
  const [mode, setMode] = useState<DojoMode>('all');
  const [selectedYear, setSelectedYear] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [shuffle, setShuffle] = useState<boolean>(true);

  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);

  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    Promise.all([questionsApi.getYears(), questionsApi.getCategories()])
      .then(([years, categories]) => {
        if (isMounted) {
          setAvailableYears(years);
          setAvailableCategories(categories);
        }
      })
      .catch((err) => {
        console.warn('Failed to load years/categories options:', err);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onStart({
      mode,
      year: selectedYear ? parseInt(selectedYear, 10) : null,
      category: mode === 'category' ? selectedCategory || null : (selectedCategory || null),
      question_count: questionCount,
      shuffle,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl p-5 sm:p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2 text-white font-bold text-base sm:text-lg">
            <SlidersHorizontal className="w-5 h-5 text-emerald-400" />
            <span>過去問道場 出題設定</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition min-w-[44px] min-h-[44px] flex items-center justify-center"
            aria-label="閉じる"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-5">
          {/* Mode Selection */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-slate-300">出題モード</label>
            <div className="grid grid-cols-2 gap-2">
              {MODES.map((item) => {
                const Icon = item.icon;
                const isSelected = mode === item.mode;
                return (
                  <button
                    key={item.mode}
                    type="button"
                    onClick={() => setMode(item.mode)}
                    className={`p-3 rounded-xl border text-left transition flex flex-col justify-between min-h-[72px] ${
                      isSelected
                        ? 'bg-emerald-950/50 border-emerald-500 text-white shadow-sm ring-1 ring-emerald-500/50'
                        : 'bg-slate-800/60 border-slate-700/60 text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <Icon className={`w-4 h-4 ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`} />
                      <span className="text-xs font-bold">{item.label}</span>
                    </div>
                    <span className="text-[10px] text-slate-400 mt-1 leading-tight">{item.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Category Dropdown (Important for Category mode) */}
          <div className="space-y-1.5">
            <label htmlFor="category-select" className="block text-xs font-semibold text-slate-300">
              分野選択 {mode === 'category' && <span className="text-emerald-400 font-normal">（必須推奨）</span>}
            </label>
            <select
              id="category-select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full min-h-[48px] bg-slate-800 border border-slate-700 rounded-xl px-3 text-sm text-white focus:outline-none focus:border-emerald-500"
            >
              <option value="">すべての分野</option>
              {availableCategories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* Year Dropdown */}
          <div className="space-y-1.5">
            <label htmlFor="year-select" className="block text-xs font-semibold text-slate-300">年度選択（任意）</label>
            <select
              id="year-select"
              value={selectedYear}
              onChange={(e) => setSelectedYear(e.target.value)}
              className="w-full min-h-[48px] bg-slate-800 border border-slate-700 rounded-xl px-3 text-sm text-white focus:outline-none focus:border-emerald-500"
            >
              <option value="">すべての年度</option>
              {availableYears.map((yr) => (
                <option key={yr} value={yr.toString()}>
                  {yr}年度
                </option>
              ))}
            </select>
          </div>

          {/* Question Count Selection */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300">出題問数</label>
            <div className="grid grid-cols-5 gap-2">
              {[5, 10, 15, 20, 25].map((cnt) => (
                <button
                  key={cnt}
                  type="button"
                  onClick={() => setQuestionCount(cnt)}
                  className={`min-h-[48px] rounded-xl border text-sm font-semibold transition ${
                    questionCount === cnt
                      ? 'bg-emerald-600 border-emerald-500 text-white'
                      : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-750'
                  }`}
                >
                  {cnt}問
                </button>
              ))}
            </div>
          </div>

          {/* Shuffle Toggle */}
          <div className="flex items-center justify-between p-3 bg-slate-800/40 border border-slate-700/50 rounded-xl">
            <div>
              <span className="text-xs font-semibold text-white">出題順序をシャッフル</span>
              <p className="text-[10px] text-slate-400">設問の順序をランダムに並び替えます</p>
            </div>
            <button
              type="button"
              onClick={() => setShuffle(!shuffle)}
              role="switch"
              aria-checked={shuffle}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none min-w-[44px] ${
                shuffle ? 'bg-emerald-600' : 'bg-slate-700'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  shuffle ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Submit Action */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 min-h-[52px] bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition active:scale-[0.98] shadow-lg disabled:opacity-50"
            >
              <Play className="w-5 h-5 fill-white" />
              <span>{isLoading ? 'セッション生成中...' : '演習を開始する'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
