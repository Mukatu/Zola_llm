// Communs de connaissance (niveau 3) — consentement opt-in + extraction.
import { api } from "./api";

export interface OptinState {
  tenant_id?: string;
  enabled: boolean;
  scopes: string[];
  updated_by?: string | null;
}

export interface ExtractResult {
  scanned: number;
  nouveaux: number;
  corrobores: number;
  raison?: string;
}

export function getOptin(): Promise<OptinState> {
  return api("/v1/commons/optin");
}

export function setOptin(enabled: boolean, scopes: string[]): Promise<OptinState> {
  return api("/v1/commons/optin", { method: "PUT", body: { enabled, scopes } });
}

export function runExtraction(): Promise<ExtractResult> {
  return api("/v1/commons/extract", { body: {} });
}

// ----- Curation (réservé au scope commons:curate) -----
export interface Candidate {
  id: string;
  type: string;
  domaine: string;
  payload: { domaine?: string; question?: string; reponse?: string };
  occurrences: number;
  status: string;
  first_seen: string | null;
}

export function listCandidates(
  eligibleOnly = true,
): Promise<{ k_anonymat: number; total: number; candidats: Candidate[] }> {
  return api(`/v1/commons/candidates?eligible_only=${eligibleOnly}`);
}

export function validateCandidate(id: string): Promise<Candidate> {
  return api(`/v1/commons/candidates/${id}/validate`, { body: {} });
}

export function rejectCandidate(id: string): Promise<Candidate> {
  return api(`/v1/commons/candidates/${id}/reject`, { body: {} });
}
