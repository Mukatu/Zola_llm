"use client";

import { useEffect, useState } from "react";
import { Wifi, WifiOff, Search, KeyRound, LogOut } from "lucide-react";
import { useZola } from "./ConfigProvider";
import { getToken, setToken, fetchDevToken, logout } from "@/lib/auth";

export function TopBar() {
  const { config, online } = useZola();
  const surface = config.profil === "cortex" ? "Zolacortex" : "Zolabox";
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    if (getToken()) {
      setAuthed(true);
    } else {
      // Auto-login de développement : l'app se connecte seule (aucun jeton à coller).
      void fetchDevToken().then((t) => setAuthed(Boolean(t)));
    }
  }, []);

  function manageToken() {
    const current = getToken() ?? "";
    const t = window.prompt("Jeton d'accès API (Bearer). Laissez vide pour déconnecter.", current);
    if (t === null) return;
    setToken(t.trim() || null);
    setAuthed(Boolean(t.trim()));
  }

  async function onLogout() {
    if (!window.confirm("Se déconnecter de ZolaOS ?")) return;
    await logout(); // efface les cookies de session côté serveur puis renvoie vers /login
  }

  const initiale = (config.branding.nom_affichage.trim()[0] ?? "Z").toUpperCase();

  return (
    <header className="flex h-14 items-center gap-4 bg-navy px-4 text-white">
      <div className="flex items-center gap-2.5 font-semibold">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-sm text-white shadow-sm shadow-primary/40">
          {initiale}
        </span>
        <span className="truncate">{config.branding.nom_affichage}</span>
        <span className="rounded-md bg-white/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-white/70">{surface}</span>
      </div>

      <button className="ml-2 hidden items-center gap-2 rounded-xl bg-white/10 px-3 py-1.5 text-sm text-white/70 transition hover:bg-white/[0.15] sm:flex">
        <Search className="h-4 w-4" /> Rechercher
        <kbd className="ml-2 rounded bg-white/10 px-1.5 text-[10px] ring-1 ring-white/15">⌘K</kbd>
      </button>

      <div className="ml-auto flex items-center gap-3">
        <button onClick={manageToken} title={authed ? "Authentifié — gérer le jeton" : "Configurer le jeton d'accès"}
          className={"flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition " + (authed ? "bg-mint/20 text-mint" : "bg-white/10 text-white/70 hover:bg-white/[0.15]")}>
          <KeyRound className="h-3.5 w-3.5" /> {authed ? "Connecté" : "Jeton"}
        </button>
        <span className="rounded-md bg-white/10 px-2 py-1 text-xs font-medium uppercase text-white/70">{config.locale}</span>
        {online ? (
          <Wifi className="h-4 w-4 text-mint" aria-label="En ligne" />
        ) : (
          <WifiOff className="h-4 w-4 text-amber-400" aria-label="Hors-ligne" />
        )}
        <button
          onClick={onLogout}
          title="Se déconnecter"
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-white/70 transition hover:bg-white/[0.15] hover:text-white"
        >
          <LogOut className="h-3.5 w-3.5" />
        </button>
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary to-primary/50 ring-2 ring-white/10" />
      </div>
    </header>
  );
}
