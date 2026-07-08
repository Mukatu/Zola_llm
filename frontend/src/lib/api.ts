// Client API typé minimal vers l'API ZolaOS (/v1).
import { fetchDevToken, getToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface ApiOptions {
  method?: string;
  body?: unknown;
  token?: string;
  signal?: AbortSignal;
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const send = async (tok?: string): Promise<Response> => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    const t = tok ?? opts.token ?? getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    return fetch(`${API_BASE}${path}`, {
      method: opts.method || (opts.body !== undefined ? "POST" : "GET"),
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
    });
  };

  let r = await send();
  // Jeton absent/expiré → auto-login dev puis nouvel essai (transparent en local).
  if (r.status === 401 && !opts.token) {
    const fresh = await fetchDevToken();
    if (fresh) r = await send(fresh);
  }
  if (!r.ok) throw new ApiError(r.status, await r.text().catch(() => ""));
  return (await r.json()) as T;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API ${status}: ${detail.slice(0, 200)}`);
  }
}
