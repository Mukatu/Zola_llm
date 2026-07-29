// Client typé — journal d'audit du cockpit cabinet (Zolacortex). Trace les
// événements de gouvernance (licences, comptes, boxes, missions...).
// Endpoint /v1/cortex/audit(/actions).
import { api } from "./api";

export interface AuditEvent {
  id: number;
  occurred_at: string;
  category: string;
  event: string;
  actor_type: string;
  actor_id: string | null;
  tenant_id: string | null;
  severity: string;
  payload: Record<string, unknown>;
}

export interface ListAuditParams {
  event?: string;
  category?: string;
  tenantId?: string;
  limit?: number;
}

export function listAudit(params: ListAuditParams = {}): Promise<AuditEvent[]> {
  const qs = new URLSearchParams();
  if (params.event) qs.set("event", params.event);
  if (params.category) qs.set("category", params.category);
  if (params.tenantId) qs.set("tenant_id", params.tenantId);
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  const query = qs.toString();
  return api<AuditEvent[]>("/v1/cortex/audit" + (query ? "?" + query : ""));
}

export function listAuditActions(): Promise<string[]> {
  return api<string[]>("/v1/cortex/audit/actions");
}
