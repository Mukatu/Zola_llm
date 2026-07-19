// Appel à l'orchestrateur génératif (/v1/query) — route vers le bon agent.
// Le LLM doit tourner côté backend ; auth via NEXT_PUBLIC_API_TOKEN (Bearer).
import { api, ApiError } from "./api";
import { fetchDevToken, getToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface Citation {
  index: number;
  source_uri: string;
  source_id: string | null;
  similarity: number;
  schema_rag?: string | null; // corpus de la citation (lien Bibliothèque)
  extrait?: string; // texte verbatim du chunk cité (affiché sous la réponse)
}
/**
 * Ancrage de la réponse :
 *  - "sourced"   : appuyée sur le corpus, citations à l'appui
 *  - "abstained" : corpus muet sur un pôle réglementé → refus assumé de répondre
 *  - "unsourced" : le modèle a répondu librement, sans aucune source → à signaler
 */
export type Grounding = "sourced" | "abstained" | "unsourced";

interface AgentResp { pole: string; content: string; citations?: Citation[]; grounding?: Grounding }
interface QueryResponse { request_id: string; responses: AgentResp[] }

export interface QueryResult {
  content: string;
  pole?: string;
  requestId?: string;
  citations: Citation[];
  grounding: Grounding;
}

export async function runQuery(query: string): Promise<QueryResult> {
  const r = await api<QueryResponse>("/v1/query", { body: { query } });
  const first = r.responses?.[0];
  return {
    content: first?.content ?? "(réponse vide)",
    pole: first?.pole,
    requestId: r.request_id,
    citations: first?.citations ?? [],
    grounding: first?.grounding ?? "unsourced",
  };
}

export interface StreamHandlers {
  onRouting?: (pole: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onToken?: (text: string) => void;
  onGrounding?: (grounding: Grounding) => void;
}

/**
 * Même requête que `runQuery`, en SSE (`/v1/query/stream`) : la réponse s'affiche
 * au fil de l'eau au lieu d'attendre la génération complète. Les citations
 * arrivent avant le premier token — le retrieve est fini bien avant le modèle.
 * Résout avec le résultat complet une fois le flux terminé.
 */
export interface StreamOptions {
  signal?: AbortSignal;
  deep?: boolean; // mode « réponse approfondie » → modèle lourd (70B), plus lent
}

export async function streamQuery(
  query: string,
  handlers: StreamHandlers = {},
  opts: StreamOptions = {},
): Promise<QueryResult> {
  const send = async (tok?: string): Promise<Response> => {
    const t = tok ?? getToken();
    return fetch(`${API_BASE}/v1/query/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(t ? { Authorization: `Bearer ${t}` } : {}),
      },
      body: JSON.stringify({ query, deep: opts.deep ?? false }),
      signal: opts.signal,
    });
  };

  let r = await send();
  if (r.status === 401) {
    const fresh = await fetchDevToken();
    if (fresh) r = await send(fresh);
  }
  if (!r.ok || !r.body) throw new ApiError(r.status, await r.text().catch(() => ""));

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let content = "";
  let pole: string | undefined;
  let requestId: string | undefined;
  let citations: Citation[] = [];
  let grounding: Grounding = "unsourced";
  let failure: string | undefined;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // Les événements SSE sont séparés par une ligne vide ; le dernier morceau
    // peut être incomplet → on le garde en tampon pour le tour suivant.
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const ev = JSON.parse(line.slice(6));
      if (ev.type === "routing") {
        pole = ev.pole;
        handlers.onRouting?.(ev.pole);
      } else if (ev.type === "citations") {
        citations = (ev.citations ?? []).map((c: Citation) => ({ ...c, schema_rag: ev.rag_schema }));
        handlers.onCitations?.(citations);
      } else if (ev.type === "token") {
        content += ev.text;
        handlers.onToken?.(ev.text);
      } else if (ev.type === "done") {
        requestId = ev.request_id;
        grounding = ev.grounding ?? "unsourced";
        handlers.onGrounding?.(grounding);
      } else if (ev.type === "error") {
        failure = ev.detail;
      }
    }
  }

  if (failure) throw new ApiError(502, failure);
  return { content: content || "(réponse vide)", pole, requestId, citations, grounding };
}
