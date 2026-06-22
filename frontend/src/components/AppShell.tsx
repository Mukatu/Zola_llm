"use client";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { useZola } from "./ConfigProvider";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { online, t } = useZola();
  return (
    <div className="flex h-screen flex-col">
      <TopBar />
      {!online && (
        <div className="bg-amber-100 px-4 py-1.5 text-center text-xs font-medium text-amber-800">
          {t("offline.banner")}
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
