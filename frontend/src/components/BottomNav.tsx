import React from 'react';
import {
  Swords,
  Search,
  MessageSquareQuote,
  BookMarked,
  BarChart3,
} from 'lucide-react';

export type TabKey = 'practice' | 'questions' | 'chat' | 'insights' | 'analytics';

interface BottomNavProps {
  currentTab: TabKey;
  onSelectTab: (tab: TabKey) => void;
}

interface NavItem {
  key: TabKey;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string | number;
}

const NAV_ITEMS: NavItem[] = [
  { key: 'practice', label: '道場', icon: Swords },
  { key: 'questions', label: '検索', icon: Search },
  { key: 'chat', label: 'AI質問', icon: MessageSquareQuote },
  { key: 'insights', label: 'ナレッジ', icon: BookMarked },
  { key: 'analytics', label: '分析', icon: BarChart3 },
];

export const BottomNav: React.FC<BottomNavProps> = ({ currentTab, onSelectTab }) => {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-[#0F172A]/95 backdrop-blur-md border-t border-slate-800 pb-safe">
      <div className="max-w-md mx-auto flex items-center justify-around px-2 py-1">
        {NAV_ITEMS.map((item) => {
          const isActive = currentTab === item.key;
          const Icon = item.icon;

          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onSelectTab(item.key)}
              className={`flex-1 flex flex-col items-center justify-center min-h-[50px] min-w-[48px] py-1 px-1 rounded-xl transition-all select-none active:scale-90 ${
                isActive
                  ? 'text-emerald-400 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="relative flex items-center justify-center">
                <Icon
                  className={`w-5 h-5 transition-transform duration-200 ${
                    isActive ? 'scale-110 text-emerald-400' : 'text-slate-400'
                  }`}
                />
                {isActive && (
                  <span className="absolute -bottom-1 w-1.5 h-1.5 rounded-full bg-emerald-400" />
                )}
              </div>
              <span
                className={`text-[10px] mt-1 tracking-tight transition-colors ${
                  isActive ? 'text-emerald-400' : 'text-slate-400'
                }`}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
