import React from 'react';
import { HelpCircle, Swords } from 'lucide-react';

interface NotFoundScreenProps {
  onGoHome: () => void;
}

export const NotFoundScreen: React.FC<NotFoundScreenProps> = ({ onGoHome }) => {
  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center text-center px-4 space-y-4">
      <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400">
        <HelpCircle className="w-8 h-8 text-amber-400" />
      </div>
      <div>
        <h2 className="text-xl font-bold text-white">ページが見つかりません</h2>
        <p className="text-sm text-slate-400 mt-1">
          指定された URL パスは存在しないか、移動した可能性があります。
        </p>
      </div>

      <button
        type="button"
        onClick={onGoHome}
        className="min-h-[48px] px-6 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl shadow-md flex items-center gap-2 active:scale-95 transition"
      >
        <Swords className="w-4 h-4" />
        <span>過去問道場へ戻る</span>
      </button>
    </div>
  );
};
