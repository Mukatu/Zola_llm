// Client typé — surface cabinet (Zolacortex) : gestion des missions.
// Zero Trust : la mission donne un accès éphémère, scopé et anonymisé à la
// Zolabox du client. Endpoints /v1/cortex/* (profil cortex, auth requise).
import { api } from "./api";

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
