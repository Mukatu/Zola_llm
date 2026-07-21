// Jeton d'accès API (Bearer, mode dev) + session par cookies httpOnly (production).
const KEY = "zo_token";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface User {
  email: string;
  display_name: string;
  tenant_id: string | null;
  country: string;
  role: string;
  scopes: string[];
}

export function getToken(): string | undefined {
  if (typeof window !== "undefined") {
    const t = window.localStorage.getItem(KEY);
    if (t) return t;
  }
  return process.env.NEXT_PUBLIC_API_TOKEN || undefined;
}

export function setToken(t: string | null): void {
  if (typeof window === "undefined") return;
  if (t) window.localStorage.setItem(KEY, t);
  else window.localStorage.removeItem(KEY);
}

export function hasToken(): boolean {
  return Boolean(getToken());
}

// Le cookie zo_csrf est le seul des trois (access/refresh/csrf) lisible par JS :
// on le rejoue en en-tête sur les requêtes mutantes pour prouver l'origine
// (SameSite=lax protège les POST cross-site mais pas les sous-domaines/proxies).
export function getCsrf(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const m = document.cookie.match(/(?:^|;\s*)zo_csrf=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : undefined;
}

export async function login(email: string, password: string): Promise<User> {
  const r = await fetch(`${API_BASE}/v1/auth/login`, {
    method: "POST",
    credentials: "include", // reçoit les cookies zo_access/zo_refresh/zo_csrf
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (r.status === 401) throw new Error("Identifiants invalides.");
  if (r.status === 429) throw new Error("Trop de tentatives, réessayez dans quelques minutes.");
  if (!r.ok) throw new Error("Connexion impossible pour le moment.");
  const d = (await r.json()) as { user: User; csrf_token: string };
  return d.user;
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": getCsrf() ?? "" },
    });
  } finally {
    // Purge un éventuel jeton dev pour ne pas ré-authentifier silencieusement
    // via fetchDevToken() juste après la déconnexion.
    setToken(null);
    window.location.assign("/login");
  }
}

// Renouvelle l'access token à partir du cookie refresh (le serveur le fait tourner).
// L'access token est court : sans ce renouvellement, la session mourrait au bout
// d'une heure et l'utilisateur serait éjecté vers /login en pleine action.
// `false` = refresh lui aussi expiré/révoqué → reconnexion nécessaire.
export async function refreshSession(): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": getCsrf() ?? "" },
    });
    return r.ok;
  } catch {
    return false;
  }
}

export async function me(): Promise<User | null> {
  try {
    let r = await fetch(`${API_BASE}/v1/auth/me`, { credentials: "include" });
    // Access token expiré mais refresh encore valide → on renouvelle et on réessaie,
    // sinon l'app croirait l'utilisateur déconnecté et le renverrait vers /login
    // alors que sa session est parfaitement récupérable.
    if (r.status === 401 && (await refreshSession())) {
      r = await fetch(`${API_BASE}/v1/auth/me`, { credentials: "include" });
    }
    if (!r.ok) return null;
    return (await r.json()) as User;
  } catch {
    return null;
  }
}

// Idempotent : évite une boucle de redirection si on est déjà sur /login.
export function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  window.location.assign("/login?next=" + encodeURIComponent(window.location.pathname));
}

// Auto-login de développement : récupère un jeton local (sans identifiants) et le
// stocke. 404 hors dev → renvoie null (un vrai login sera requis).
export async function fetchDevToken(): Promise<string | null> {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  try {
    const r = await fetch(`${base}/v1/auth/dev-token`, { method: "POST" });
    if (!r.ok) return null;
    const d = (await r.json()) as { token?: string };
    if (d.token) {
      setToken(d.token);
      return d.token;
    }
  } catch {
    /* backend indisponible */
  }
  return null;
}
