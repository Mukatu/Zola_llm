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
