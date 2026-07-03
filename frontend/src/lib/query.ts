// Appel à l'orchestrateur génératif (/v1/query) — route vers le bon agent.
// Le LLM doit tourner côté backend ; auth via NEXT_PUBLIC_API_TOKEN (Bearer).
import { api } from "./api";

export interface Citation {
  index: number;
  source_uri: string;
  source_id: string | null;
  similarity: number;
}
interface AgentResp { pole: string; content: string; citations?: Citation[] }
interface QueryResponse { request_id: string; responses: AgentResp[] }

export interface QueryResult {
  content: string;
  pole?: string;
  requestId?: string;
  citations: Citation[];
}

export async function runQuery(query: string): Promise<QueryResult> {
  const r = await api<QueryResponse>("/v1/query", { body: { query } });
  const first = r.responses?.[0];
  return {
    content: first?.content ?? "(réponse vide)",
    pole: first?.pole,
    requestId: r.request_id,
    citations: first?.citations ?? [],
  };
}
