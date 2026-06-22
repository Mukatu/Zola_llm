"use client";

import { Wifi, WifiOff, Search } from "lucide-react";
import { useZola } from "./ConfigProvider";

export function TopBar() {
  const { config, online } = useZola();
  const surface = config.profil === "cortex" ? "Zolacortex" : "Zolabox";

  return (
    <header className="flex h-14 items-center gap-4 border-b border-black/5 bg-surface px-4">
      <div className="flex items-center gap-2 font-semibold">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary text-white">Z</span>
        <span className="truncate">{config.branding.nom_affichage}</span>
        <span className="rounded-md bg-black/5 px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted">{surface}</span>
      </div>

      <button className="ml-2 hidden items-center gap-2 rounded-xl bg-black/5 px-3 py-1.5 text-sm text-muted hover:bg-black/10 sm:flex">
        <Search className="h-4 w-4" /> Rechercher
        <kbd className="ml-2 rounded bg-white px-1.5 text-[10px] ring-1 ring-black/10">⌘K</kbd>
      </button>

      <div className="ml-auto flex items-center gap-3">
        <span className="rounded-md bg-black/5 px-2 py-1 text-xs font-medium uppercase">{config.locale}</span>
        {online ? (
          <Wifi className="h-4 w-4 text-emerald-600" aria-label="En ligne" />
        ) : (
          <WifiOff className="h-4 w-4 text-amber-600" aria-label="Hors-ligne" />
        )}
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary to-primary/60" />
      </div>
    </header>
  );
}
