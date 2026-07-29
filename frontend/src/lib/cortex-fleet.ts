// Client typé — supervision de la flotte (Zolacortex) : vue d'ensemble des boxes
// clients (connexion, licence, missions). Endpoint /v1/cortex/fleet.
import { api } from "./api";

export interface FleetSummary {
  clients: number;
  boxes_connected: number;
  licenses_active: number;
  licenses_expiring_soon: number;
  licenses_expired_or_revoked: number;
  licenses_none: number;
}

export type LicenseStatus = "active" | "expired" | "revoked" | "none";

export interface FleetRow {
  tenant_id: string;
  name: string;
  country: string;
  is_active: boolean;
  box_provisioned: boolean;
  box_connected: boolean;
  license_status: LicenseStatus;
  license_tier: string | null;
  license_expires_at: string | null;
  license_days_left: number | null;
  active_missions: number;
}

export interface FleetResponse {
  summary: FleetSummary;
  rows: FleetRow[];
}

export function getFleet(expiringDays?: number): Promise<FleetResponse> {
  const qs = expiringDays ? "?expiring_days=" + expiringDays : "";
  return api<FleetResponse>("/v1/cortex/fleet" + qs);
}
