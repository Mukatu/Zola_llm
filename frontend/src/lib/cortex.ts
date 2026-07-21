// Client typé — surface cabinet (Zolacortex) : gestion des missions.
// Zero Trust : la mission donne un accès éphémère, scopé et anonymisé à la
// Zolabox du client. Endpoints /v1/cortex/* (profil cortex, auth requise).
import { api, ApiError } from "./api";
import { getCsrf } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface MissionSummary {
  mission_id: string;
  client_tenant_id: string;
  offre: string;
  status: string;
  started_at: string;
  expires_at: string;
  revoked_at: string | null;
  scope_tags: string[];
}

export interface CreateMissionInput {
  client_tenant_id: string;
  offre: string;
  scope_tags: string[];
  ttl_hours: number;
}

export interface CreateMissionResult {
  mission_id: string;
  token: string;
  expires_at: string;
  offre: string;
  scope_tags: string[];
}

export function listMissions(): Promise<MissionSummary[]> {
  return api<MissionSummary[]>("/v1/cortex/missions");
}

export function createMission(body: CreateMissionInput): Promise<CreateMissionResult> {
  return api<CreateMissionResult>("/v1/cortex/missions", { body });
}

export function revokeMission(id: string): Promise<{ mission_id: string; status: string; revoked_at: string }> {
  return api("/v1/cortex/missions/" + id + "/revoke", { method: "POST", body: {} });
}

// Bundle produit par l'overlay Polaris : une synthèse + des findings dont les
// clés dépendent de l'offre (RH, fiscal, générique…) — jamais figées ici.
export interface AuditResult {
  synthese: string;
  findings: Record<string, unknown>[];
  [k: string]: unknown;
}

export interface Citation {
  index: number;
  source_id: string | null;
  source_uri: string;
  similarity: number;
}

// Origine du corpus interrogé par l'audit — distingue les données réelles du
// client (via la Zolabox, tunnel ou accès direct) du corpus local du cortex.
export type RetrievalSource = "remote_box_tunnel" | "remote_box" | "local_cortex";

export interface LastAudit {
  offre: string;
  query: string;
  ran_at: string;
  result: AuditResult;
  citations: Citation[];
  retrieval: RetrievalSource;
}

export interface MissionDetail {
  mission_id: string;
  cabinet_tenant_id: string;
  client_tenant_id: string;
  offre: string;
  status: string;
  started_at: string;
  expires_at: string;
  revoked_at: string | null;
  scope_tags: string[];
  last_audit: LastAudit | null;
}

export interface AuditInput {
  query?: string;
  deep?: boolean;
}

export interface AuditResponse {
  mission_id: string;
  offre: string;
  ran_at: string;
  result: AuditResult;
  citations: Citation[];
  retrieval: RetrievalSource;
}

export function getMission(id: string): Promise<MissionDetail> {
  return api<MissionDetail>("/v1/cortex/missions/" + id);
}

export function runAudit(id: string, input: AuditInput): Promise<AuditResponse> {
  return api<AuditResponse>("/v1/cortex/missions/" + id + "/audit", { body: input });
}

// Le rapport est un binaire (.docx) : `api()` suppose du JSON, donc on refait
// l'appel fetch nous-mêmes (mêmes règles d'auth : cookie de session + CSRF).
export async function downloadReport(id: string): Promise<void> {
  const res = await fetch(API_BASE + "/v1/cortex/missions/" + id + "/report", {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrf() ?? "" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "rapport-mission-" + id + ".docx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
