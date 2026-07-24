// Client API du pôle Cyber-défense (/v1/cyber) — audit de durcissement
// (défensif, déterministe, sans persistance de secrets). Calque de fintech.ts.
import { api } from "./api";

export type Fonction = "identify" | "protect" | "detect" | "respond" | "recover";
export type Severite = "critical" | "high" | "medium" | "low";
export type Statut = "conforme" | "non_conforme" | "a_verifier";

export interface Controle {
  cle: string;
  libelle: string;
  fonction: Fonction;
  severite: Severite;
  remediation: string;
}

export interface Baseline {
  controles: Controle[];
  reference_cadre: string;
}

// Les 15 clés exactes de la baseline (miroir du backend, pour typer le formulaire).
export const CONTROLE_KEYS = [
  "inventaire_actifs",
  "registre_donnees_perso",
  "mfa_admin",
  "ssh_root_desactive",
  "politique_mdp",
  "moindre_privilege",
  "chiffrement_repos",
  "tls_applique",
  "pare_feu_deny",
  "correctifs_a_jour",
  "protection_poste",
  "journalisation",
  "revue_journaux",
  "plan_reponse_incident",
  "sauvegardes_testees",
] as const;

export type ControleKey = (typeof CONTROLE_KEYS)[number];

export type ConfigAudit = Record<ControleKey, boolean | null>;

export const EMPTY_CONFIG_AUDIT: ConfigAudit = CONTROLE_KEYS.reduce((acc, k) => {
  acc[k] = null;
  return acc;
}, {} as ConfigAudit);

export interface Finding {
  cle: string;
  libelle: string;
  fonction: Fonction;
  severite: Severite;
  statut: Statut;
  remediation: string;
}

export interface FonctionSynthese {
  conforme: number;
  non_conforme: number;
  a_verifier: number;
}

export interface AuditResult {
  score_conformite: string;
  nb_conforme: number;
  nb_non_conforme: number;
  nb_a_verifier: number;
  niveau: "critical" | "high" | "medium" | "low" | "aucun";
  par_fonction: Record<string, FonctionSynthese>;
  findings: Finding[];
  reference_cadre: string;
}

export interface CyberAudit {
  id: string;
  tenant_id: string;
  cible: string;
  score_conformite: string;
  nb_conforme: number;
  nb_non_conforme: number;
  nb_a_verifier: number;
  niveau: string;
  config: ConfigAudit;
  resultat: AuditResult;
  commentaire: string | null;
  country: string;
  created_at: string | null;
}

export async function getBaseline(): Promise<Baseline> {
  return api<Baseline>("/v1/cyber/baseline");
}

export async function cyberAudit(config: ConfigAudit): Promise<AuditResult> {
  return api<AuditResult>("/v1/cyber/audit", { body: config });
}

export async function createCyberAudit(body: { cible: string; config: ConfigAudit }): Promise<CyberAudit> {
  return api<CyberAudit>("/v1/cyber/audits", { body });
}

export async function listCyberAudits(): Promise<{ audits: CyberAudit[] }> {
  return api<{ audits: CyberAudit[] }>("/v1/cyber/audits");
}

export async function getCyberAudit(id: string): Promise<CyberAudit> {
  return api<CyberAudit>(`/v1/cyber/audits/${id}`);
}

export async function deleteCyberAudit(id: string): Promise<{ status: string }> {
  return api<{ status: string }>(`/v1/cyber/audits/${id}`, { method: "DELETE" });
}
