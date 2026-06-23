// Types + chargement de la configuration de personnalisation (/v1/config).

export interface Branding {
  nom_affichage: string;
  couleur_primaire: string; // #RRGGBB
  logo_uri: string | null;
}

export interface TenantConfig {
  tenant_id: string | null;
  profil: "box" | "cortex";
  personnalisable: boolean;
  modules_actifs: string[];
  branding: Branding;
  locale: "fr" | "ln" | "kg";
  champs_personnalises: Record<string, string>;
  connecteurs_actifs: string[];
}

export const DEFAULT_CONFIG: TenantConfig = {
  tenant_id: null,
  profil: (process.env.NEXT_PUBLIC_SURFACE as "box" | "cortex") || "box",
  personnalisable: true,
  modules_actifs: ["droit.ohada", "erp.rh", "erp.finance", "bi.pilotage"],
  branding: { nom_affichage: "ZolaOS", couleur_primaire: "#0B5FFF", logo_uri: null },
  locale: "fr",
  champs_personnalises: {},
  connecteurs_actifs: [],
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function fetchConfig(tenantId?: string): Promise<TenantConfig> {
  const url = new URL("/v1/config", API_BASE);
  if (tenantId) url.searchParams.set("tenant_id", tenantId);
  const r = await fetch(url.toString(), { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`config ${r.status}`);
  return (await r.json()) as TenantConfig;
}

export async function saveConfig(tenantId: string, overrides: Partial<TenantConfig>): Promise<TenantConfig> {
  const r = await fetch(new URL("/v1/config", API_BASE).toString(), {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ tenant_id: tenantId, ...overrides }),
  });
  if (!r.ok) throw new Error(`save ${r.status}`);
  return (await r.json()) as TenantConfig;
}

/** Convertit #RRGGBB en triplet "r g b" pour les variables CSS Tailwind. */
export function hexToRgbTriplet(hex: string): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return "11 95 255";
  const n = parseInt(m[1], 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}
