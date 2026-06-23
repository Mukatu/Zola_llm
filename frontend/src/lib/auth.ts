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
