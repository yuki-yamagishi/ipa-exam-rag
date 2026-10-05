import React from 'react';
import { Header } from './Header';
import { BottomNav, type TabKey } from './BottomNav';
import type { AuthStatusResponse } from '../types';

interface LayoutProps {
  currentTab: TabKey;
  onSelectTab: (tab: TabKey) => void;
  authStatus?: AuthStatusResponse | null;
  onOpenSettings?: () => void;
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({
  currentTab,
  onSelectTab,
  authStatus,
  onOpenSettings,
  children,
}) => {
  return (
    <div className="flex flex-col min-h-screen bg-[#0B0F19] text-slate-100">
      <Header authStatus={authStatus} onOpenSettings={onOpenSettings} />
      <main className="flex-1 max-w-lg w-full mx-auto px-4 pt-3 pb-24">
        {children}
      </main>
      <BottomNav currentTab={currentTab} onSelectTab={onSelectTab} />
    </div>
  );
};
