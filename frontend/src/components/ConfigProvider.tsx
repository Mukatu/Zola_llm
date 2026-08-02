"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { DEFAULT_CONFIG, fetchConfig, hexToRgbTriplet, saveConfig, type TenantConfig } from "@/lib/config";
import { makeT } from "@/lib/i18n";
import { fetchDevToken, getToken, me, redirectToLogin, type User } from "@/lib/auth";

const TENANT = "local"; // box mono-client (DB persistance plus tard)

interface Ctx {
  config: TenantConfig;
  loading: boolean;
  online: boolean;
  user: User | null;
  t: (key: string) => string;
  save: (overrides: Partial<TenantConfig>) => Promise<void>;
}

const ConfigContext = createContext<Ctx | null>(null);

// Vrai si l'utilisateur courant porte le scope demandé (ex. "admin:users").
// Simple gate UX : la sécurité réelle est appliquée côté backend.
export function hasScope(user: User | null, scope: string): boolean {
  return Boolean(user?.scopes.includes(scope));
}

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<TenantConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [online, setOnline] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchConfig(TENANT)
      .then((c) => { if (alive) { setConfig(c); setOnline(true); } })
      .catch(() => { if (alive) setOnline(false); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    let alive = true;
    me()
      .then((u) => { if (alive) setUser(u); })
      .catch(() => { if (alive) setUser(null); })
      .finally(() => { if (alive) setAuthChecked(true); });
    return () => { alive = false; };
  }, []);

  // Garde d'authentification : une fois la session vérifiée, si l'utilisateur
  // n'est ni connecté (cookie) ni porteur d'un jeton (dev/manuel), on tente
  // l'auto-login dev puis, à défaut, on renvoie vers /login. Empêche d'atteindre
  // l'app sans s'authentifier (le shell s'affichait sinon avant tout appel protégé).
  useEffect(() => {
    if (!authChecked || user) return;
    let alive = true;
    (async () => {
      if (getToken()) return; // jeton déjà présent (dev/manuel)
      const dev = await fetchDevToken(); // auto-login dev (404 → null hors dev)
      if (alive && !dev) redirectToLogin();
    })();
    return () => { alive = false; };
  }, [authChecked, user]);

  useEffect(() => {
    document.documentElement.style.setProperty("--zo-primary", hexToRgbTriplet(config.branding.couleur_primaire));
    document.documentElement.lang = config.locale;
  }, [config]);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  async function save(overrides: Partial<TenantConfig>) {
    const updated = await saveConfig(TENANT, overrides);
    setConfig(updated);
  }

  return (
    <ConfigContext.Provider value={{ config, loading, online, user, t: makeT(config.locale), save }}>
      {children}
    </ConfigContext.Provider>
  );
}

export function useZola(): Ctx {
  const c = useContext(ConfigContext);
  if (!c) throw new Error("useZola doit être utilisé dans <ConfigProvider>");
  return c;
}
