// Client typé — Secrétariat sociétaire : registre des mandats (organes de gestion,
// AUSCGIE), résolutions d'AG/CA (PV) et échéancier légal associé
// (/v1/erp/mandates|resolutions|corporate/echeances).
import { api } from "./api";

export type FonctionMandat =
  | "gerant"
  | "administrateur"
  | "president_ca"
  | "directeur_general"
  | "commissaire_comptes"
  | "autre";

export type StatutMandat = "actif" | "expire" | "revoque";

export type TypeReunion = "AGO" | "AGE" | "CA";

export type Urgence = "high" | "medium" | "low";

export interface Mandate {
  id: string;
  tenant_id: string;
  titulaire: string;
  fonction: FonctionMandat;
  date_nomination: string;
  duree_annees: number;
  organe: string | null;
  statut: StatutMandat;
  country: string;
}

export interface Resolution {
  id: string;
  tenant_id: string;
  type_reunion: TypeReunion;
  date_reunion: string;
  objet: string;
  decision: string | null;
  reference_pv: string | null;
  quorum: string | null;
  country: string;
}

export interface SecretariatAlerte {
  categorie: "mandat" | "ago";
  reference: string;
  libelle: string;
  date_cible: string;
  jours_restants: number;
  urgence: Urgence;
}

export function listMandates(): Promise<{ mandates: Mandate[] }> {
  return api("/v1/erp/mandates");
}
export function createMandate(b: {
  titulaire: string;
  fonction: FonctionMandat;
  date_nomination: string;
  duree_annees?: number;
  organe?: string | null;
  statut?: StatutMandat;
  country?: string;
}): Promise<Mandate> {
  return api("/v1/erp/mandates", { body: b });
}
export function updateMandate(id: string, patch: Partial<Mandate>): Promise<Mandate> {
  return api(`/v1/erp/mandates/${id}`, { method: "PATCH", body: patch });
}
export function deleteMandate(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/mandates/${id}`, { method: "DELETE" });
}

export function listResolutions(): Promise<{ resolutions: Resolution[] }> {
  return api("/v1/erp/resolutions");
}
export function createResolution(b: {
  type_reunion: TypeReunion;
  date_reunion: string;
  objet: string;
  decision?: string | null;
  reference_pv?: string | null;
  quorum?: string | null;
  country?: string;
}): Promise<Resolution> {
  return api("/v1/erp/resolutions", { body: b });
}
export function updateResolution(id: string, patch: Partial<Resolution>): Promise<Resolution> {
  return api(`/v1/erp/resolutions/${id}`, { method: "PATCH", body: patch });
}
export function deleteResolution(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/resolutions/${id}`, { method: "DELETE" });
}

export function getEcheances(params?: {
  date_cloture?: string;
  horizon_jours?: number;
}): Promise<{ alertes: SecretariatAlerte[] }> {
  const q: string[] = [];
  if (params?.date_cloture) q.push(`date_cloture=${params.date_cloture}`);
  if (params?.horizon_jours !== undefined) q.push(`horizon_jours=${params.horizon_jours}`);
  const qs = q.length > 0 ? `?${q.join("&")}` : "";
  return api(`/v1/erp/corporate/echeances${qs}`);
}
