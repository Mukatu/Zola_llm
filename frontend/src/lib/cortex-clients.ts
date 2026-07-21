// Client typé — surface cabinet (Zolacortex) : annuaire des clients/tenants.
// Réservé au rôle admin (scope admin:users). Endpoints /v1/cortex/clients/*.
import { api } from "./api";

export interface Tenant {
  id: string;
  name: string;
  tenant_type: "cabinet" | "client";
  parent_tenant_id: string | null;
  country: string;
  is_active: boolean;
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
