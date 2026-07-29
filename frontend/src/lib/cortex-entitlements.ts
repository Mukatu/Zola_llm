// Client typé — surface cabinet (Zolacortex) : gestion des entitlements de modules.
// Réservé au rôle admin (scope admin:users). Endpoints /v1/cortex/entitlements/*.
// Pendant cabinet de l'entitlement vérifié côté box : Polaris émet/révoque/livre les
// licences signées par tenant. La clé privée d'émission ne vit que côté cortex.
import { api } from "./api";

export type GrantStatus = "active" | "expired" | "revoked";

export interface Grant {
  id: string;
  tenant_id: string;
  license_id: string;
  tier: string;
  modules: string[]; // options à la carte (EN PLUS du tier)
  effective_modules: string[]; // tier ∪ options
  status: GrantStatus;
  issued_at: string;
  expires_at: string;
  revoked_at: string | null;
  created_at: string;
}

// Vue avec le jeton signé (livrable). Renvoyée à l'émission, au détail, à la livraison.
export interface GrantWithToken extends Grant {
  token: string;
}

export interface Catalogue {
  tiers: Record<string, string[]>; // tier → modules de base
  modules: string[]; // catalogue complet des unités vendables
}

export interface IssueInput {
  tenant_id: string;
  tier: string;
  modules?: string[];
  days: number;
  license_id?: string;
}

// Tiers et modules vendables — peuple le formulaire d'émission.
export function getCatalogue(): Promise<Catalogue> {
  return api<Catalogue>("/v1/cortex/entitlements/catalogue");
}

// Licences d'un tenant (historique). active_only pour ne garder que la vivante.
export function listGrants(tenantId: string, activeOnly = false): Promise<Grant[]> {
  const qs = "?tenant_id=" + encodeURIComponent(tenantId) + (activeOnly ? "&active_only=true" : "");
  return api<Grant[]>("/v1/cortex/entitlements" + qs);
}

// Licence VIVANTE d'un tenant + son jeton (livraison). 404 si aucune → renvoie null.
export async function getActiveGrant(tenantId: string): Promise<GrantWithToken | null> {
  try {
    return await api<GrantWithToken>("/v1/cortex/entitlements/tenant/" + tenantId + "/active");
  } catch (e) {
    // 404 = pas de licence active (cas normal) → null ; toute autre erreur remonte.
    if (e && typeof e === "object" && "status" in e && (e as { status: number }).status === 404) {
      return null;
    }
    throw e;
  }
}

// Émet (signe + persiste) une licence. Révoque les licences actives antérieures du tenant.
export function issueGrant(input: IssueInput): Promise<GrantWithToken> {
  return api<GrantWithToken>("/v1/cortex/entitlements", { body: input });
}

// Révoque une licence (immédiat, irréversible).
export function revokeGrant(grantId: string): Promise<Grant> {
  return api<Grant>("/v1/cortex/entitlements/" + grantId + "/revoke", { method: "POST", body: {} });
}
