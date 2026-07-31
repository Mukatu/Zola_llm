// Client API typé minimal vers l'API ZolaOS (/v1).
import { fetchDevToken, getCsrf, getToken, me, redirectToLogin, refreshSession } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
// Ne jamais rediriger sur un 401 des endpoints d'auth eux-mêmes (login/refresh/me
// en sondage) : c'est l'appelant (page de login, vérif de session) qui gère ce cas.
const AUTH_PATH = /^\/v1\/auth\//;

export interface ApiOptions {
  method?: string;
  body?: unknown;
  token?: string;
  signal?: AbortSignal;
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const method = opts.method || (opts.body !== undefined ? "POST" : "GET");
  const mutating = ["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase());

  const send = async (tok?: string): Promise<Response> => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    const t = tok ?? opts.token ?? getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    // Le cookie zo_access suffit à l'auth (envoyé via credentials:'include'),
    // mais les requêtes mutantes doivent en plus prouver l'origine via le CSRF.
    if (mutating) {
      const csrf = getCsrf();
      if (csrf) headers["X-CSRF-Token"] = csrf;
    }
    return fetch(`${API_BASE}${path}`, {
      method,
      headers,
      credentials: "include",
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
    });
  };

  let r = await send();
  // Jeton/session absent ou expiré → auto-login dev (transparent en local) ;
  // hors dev (404 sur dev-token), on renvoie vers /login plutôt que d'échouer en silence.
  if (r.status === 401 && !opts.token) {
    // 1) Session expirée mais refresh encore valide → renouvellement silencieux.
    if (!AUTH_PATH.test(path) && (await refreshSession())) {
      r = await send();
    } else {
      // 2) Sinon repli dev (auto-login local).
      const fresh = await fetchDevToken();
      if (fresh) {
        r = await send(fresh);
      } else if (!AUTH_PATH.test(path)) {
        // 3) Avant d'éjecter vers /login : reconfirmer que la session est
        // vraiment morte. Un 401 transitoire (course au chargement, refresh
        // qui a hoqueté) ne doit pas renvoyer au login si /v1/auth/me répond
        // encore — sinon apparaît le « login furtif » (connecté puis rejeté).
        const stillValid = await me();
        if (stillValid) {
          r = await send(); // la session vit : on rejoue la requête d'origine
        } else {
          redirectToLogin();
          throw new ApiError(401, "Authentification requise.");
        }
      }
    }
  }
  if (!r.ok) throw new ApiError(r.status, await r.text().catch(() => ""));
  return (await r.json()) as T;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API ${status}: ${detail.slice(0, 200)}`);
  }
}
