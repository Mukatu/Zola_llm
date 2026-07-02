// Client typé — boucle de feedback des agents (POST /v1/feedback).
// Capture le retour utilisateur (✓/✗ + correction) sur une réponse d'agent :
// socle de l'auto-amélioration du moteur ZolaOS.
import { api } from "./api";

export type FeedbackVerdict = "up" | "down";

export interface FeedbackIn {
  agent: string;
  query: string;
  response: string;
  verdict: FeedbackVerdict;
  request_id?: string;
  correction?: string;
  context_snapshot?: Record<string, unknown>;
}

export interface FeedbackRec {
  id: string;
  agent: string;
  verdict: string;
}

export function sendFeedback(body: FeedbackIn): Promise<FeedbackRec> {
  return api("/v1/feedback", { body });
}
