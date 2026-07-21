// Client typé — surface cabinet (Zolacortex) : annuaire des clients/tenants.
// Réservé au rôle admin (scope admin:users). Endpoints /v1/cortex/clients/*.
import { api, ApiError } from "./api";
import { getCsrf } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface Tenant {
  id: string;
  name: string;
  tenant_type: "cabinet" | "client";
  parent_tenant_id: string | null;
  country: string;
  is_active: boolean;
  // Adresse de la Zolabox du client (RAG distant Zero Trust). null = pas de box.
  box_url: string | null;
  // Prefix du credential de box (non-null ⇒ box provisionnée). Le secret complet
  // n'est jamais renvoyé ici, seulement à l'émission (voir issueBoxCredential).
  box_credential_prefix: string | null;
  created_at: string;
}

export interface CreateClientInput {
  name: string;
  tenant_type?: "client" | "cabinet";
  country?: string;
  parent_tenant_id?: string;
}

export interface UpdateClientInput {
  name?: string;
  is_active?: boolean;
  parent_tenant_id?: string;
  box_url?: string;
}

export interface MissionBrief {
  id: string;
  offre: string;
  status: string;
  role: "cabinet" | "client";
  started_at: string;
  expires_at: string | null;
}

export interface ClientDetail {
  tenant: Tenant;
  missions: MissionBrief[];
}

export function listClients(type?: "client" | "cabinet"): Promise<Tenant[]> {
  const qs = type ? "?tenant_type=" + type : "";
  return api<Tenant[]>("/v1/cortex/clients" + qs);
}

export function createClient(input: CreateClientInput): Promise<Tenant> {
  return api<Tenant>("/v1/cortex/clients", { body: input });
}

export function getClient(id: string): Promise<ClientDetail> {
  return api<ClientDetail>("/v1/cortex/clients/" + id);
}

export function updateClient(id: string, patch: UpdateClientInput): Promise<Tenant> {
  return api<Tenant>("/v1/cortex/clients/" + id, { method: "PATCH", body: patch });
}

export interface BoxCredential {
  tenant_id: string;
  // Secret complet — n'est renvoyé qu'ici, une seule fois (rotation à chaque appel).
  credential: string;
  prefix: string;
}

// Émet (ou fait tourner) le credential de la box du tenant. Invalide l'ancien.
export function issueBoxCredential(id: string): Promise<BoxCredential> {
  return api<BoxCredential>("/v1/cortex/clients/" + id + "/box-credential", { method: "POST", body: {} });
}

// Révoque le credential : coupe immédiatement la box, plus de reconnexion possible.
// Réponse 204 sans corps : fetch direct (api() suppose toujours du JSON en retour).
export async function revokeBoxCredential(id: string): Promise<void> {
  const res = await fetch(API_BASE + "/v1/cortex/clients/" + id + "/box-credential", {
    method: "DELETE",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrf() ?? "" },
  });
  if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ""));
}
