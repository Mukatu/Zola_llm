// Client API du pôle GRC (/v1/grc) — registre de conformité déterministe :
// obligations, contrôles, constats + synthèse (plan de contrôle).
import { api } from "./api";

// --- Obligations -------------------------------------------------------------

export interface Obligation {
  id: string;
  tenant_id: string;
  reference: string;
  intitule: string;
  domaine: string;
  autorite: string;
  periodicite: string;
  echeance: string | null;
  base_legale: string;
  statut: string;
  country: string;
  created_at: string | null;
}

export interface ObligationInput {
  reference?: string;
  intitule: string;
  domaine?: string;
  autorite?: string;
  periodicite?: string;
  echeance?: string | null;
  base_legale?: string;
  statut?: string;
}

export async function listObligations(): Promise<Obligation[]> {
  return (await api<{ obligations: Obligation[] }>("/v1/grc/obligations")).obligations;
}

export async function createObligation(body: ObligationInput): Promise<Obligation> {
  return api<Obligation>("/v1/grc/obligations", { body });
}

export async function patchObligation(id: string, body: Partial<ObligationInput>): Promise<Obligation> {
  return api<Obligation>(`/v1/grc/obligations/${id}`, { method: "PATCH", body });
}

export async function deleteObligation(id: string): Promise<{ status: string }> {
  return api<{ status: string }>(`/v1/grc/obligations/${id}`, { method: "DELETE" });
}

// --- Contrôles -----------------------------------------------------------------

export interface Control {
  id: string;
  tenant_id: string;
  obligation_id: string | null;
  intitule: string;
  type_controle: string;
  frequence: string;
  responsable: string;
  derniere_execution: string | null;
  prochaine_execution: string | null;
  statut: string;
  country: string;
  created_at: string | null;
}

export interface ControlInput {
  obligation_id?: string | null;
  intitule: string;
  type_controle?: string;
  frequence?: string;
  responsable?: string;
  derniere_execution?: string | null;
  prochaine_execution?: string | null;
  statut?: string;
}

export async function listControls(obligationId?: string): Promise<Control[]> {
  const qs = obligationId ? `?obligation_id=${encodeURIComponent(obligationId)}` : "";
  return (await api<{ controls: Control[] }>(`/v1/grc/controls${qs}`)).controls;
}

export async function createControl(body: ControlInput): Promise<Control> {
  return api<Control>("/v1/grc/controls", { body });
}

export async function patchControl(id: string, body: Partial<ControlInput>): Promise<Control> {
  return api<Control>(`/v1/grc/controls/${id}`, { method: "PATCH", body });
}

export async function deleteControl(id: string): Promise<{ status: string }> {
  return api<{ status: string }>(`/v1/grc/controls/${id}`, { method: "DELETE" });
}

// --- Constats --------------------------------------------------------------

export interface Finding {
  id: string;
  tenant_id: string;
  obligation_id: string | null;
  control_id: string | null;
  intitule: string;
  gravite: string;
  statut: string;
  date_constat: string;
  echeance_correction: string | null;
  plan_action: string;
  responsable: string;
  country: string;
  created_at: string | null;
}

export interface FindingInput {
  obligation_id?: string | null;
  control_id?: string | null;
  intitule: string;
  gravite?: string;
  statut?: string;
  date_constat: string;
  echeance_correction?: string | null;
  plan_action?: string;
  responsable?: string;
}

export async function listFindings(obligationId?: string): Promise<Finding[]> {
  const qs = obligationId ? `?obligation_id=${encodeURIComponent(obligationId)}` : "";
  return (await api<{ findings: Finding[] }>(`/v1/grc/findings${qs}`)).findings;
}

export async function createFinding(body: FindingInput): Promise<Finding> {
  return api<Finding>("/v1/grc/findings", { body });
}

export async function patchFinding(
  id: string,
  body: Partial<Pick<FindingInput, "intitule" | "gravite" | "statut" | "echeance_correction" | "plan_action" | "responsable">>,
): Promise<Finding> {
  return api<Finding>(`/v1/grc/findings/${id}`, { method: "PATCH", body });
}

export async function deleteFinding(id: string): Promise<{ status: string }> {
  return api<{ status: string }>(`/v1/grc/findings/${id}`, { method: "DELETE" });
}

// --- Synthèse (plan de contrôle) --------------------------------------------

export interface EcheanceGrc {
  type: "obligation" | "controle";
  reference: string;
  libelle: string;
  date_limite: string;
  jours_restants: number;
}

export interface SyntheseConformite {
  nb_obligations: number;
  nb_obligations_actives: number;
  nb_obligations_sans_controle: number;
  taux_couverture: string;
  nb_controls: number;
  nb_controls_en_retard: number;
  nb_findings: number;
  nb_findings_ouverts: number;
  taux_conformite: string;
  findings_ouverts_par_gravite: { critique: number; majeur: number; mineur: number };
  obligations_par_domaine: Record<string, number>;
  echeances: EcheanceGrc[];
  alertes: string[];
}

export async function getPlanControle(horizonJours = 90): Promise<SyntheseConformite> {
  return api<SyntheseConformite>(`/v1/grc/plan-controle?horizon_jours=${horizonJours}`);
}
