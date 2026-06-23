// Appel à l'orchestrateur génératif (/v1/query) — route vers le bon agent.
// Le LLM doit tourner côté backend ; auth via NEXT_PUBLIC_API_TOKEN (Bearer).
import { api } from "./api";

interface AgentResp { pole: string; content: string }
interface QueryResponse { request_id: string; responses: AgentResp[] }

export async function runQuery(query: string): Promise<{ content: string; pole?: string }> {
  const r = await api<QueryResponse>("/v1/query", { body: { query } });
  const first = r.responses?.[0];
  return { content: first?.content ?? "(réponse vide)", pole: first?.pole };
}
