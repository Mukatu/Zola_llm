"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { AssistantDock } from "./AssistantDock";
import { useZola } from "./ConfigProvider";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { online, t } = useZola();
  const pathname = usePathname();
  // Page de login : pas de chrome applicatif (nav/assistant) avant authentification.
  if (pathname?.startsWith("/login")) return <>{children}</>;

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
      <AssistantDock />
    </div>
  );
}
