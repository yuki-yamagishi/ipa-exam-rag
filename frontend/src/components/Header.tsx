import React from 'react';
import { Settings, ShieldCheck, UserCheck } from 'lucide-react';
import type { AuthStatusResponse } from '../types';

interface HeaderProps {
  authStatus?: AuthStatusResponse | null;
  onOpenSettings?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ authStatus, onOpenSettings }) => {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-4 py-3 bg-[#0F172A]/90 backdrop-blur border-b border-slate-800">
      <div className="flex items-center space-x-2">
        <span className="text-xl">🥋</span>
        <div>
          <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
            IPA Exam RAG
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-mono">
              AM2
            </span>
          </h1>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        {authStatus?.authenticated && authStatus.user_email && (
          <div className="hidden xs:flex items-center text-xs text-slate-400 bg-slate-800/60 px-2 py-1 rounded-full border border-slate-700/50">
            <UserCheck className="w-3.5 h-3.5 text-emerald-400 mr-1" />
            <span className="max-w-[110px] truncate">{authStatus.user_email}</span>
          </div>
        )}

        {authStatus?.auth_enabled === false && (
          <div className="hidden xs:flex items-center text-[10px] text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/50">
            <ShieldCheck className="w-3 h-3 mr-1" />
            <span>Auth OFF</span>
          </div>
        )}

        <button
          type="button"
          onClick={onOpenSettings}
          className="p-2 text-slate-300 hover:text-white rounded-lg hover:bg-slate-800 active:scale-95 transition min-w-[48px] min-h-[48px] flex items-center justify-center"
          title="システム設定"
          aria-label="システム設定"
        >
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
};
