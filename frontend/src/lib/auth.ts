// Jeton d'accès API (Bearer). Stocké en localStorage ; repli sur l'env de build.
const KEY = "zo_token";

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
