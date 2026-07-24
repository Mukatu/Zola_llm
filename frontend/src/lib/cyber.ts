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

// --- Détection d'anomalies (analyse de journaux déclarés, défensif) ---------

export type TypeEvenement = "auth_success" | "auth_failure" | "access" | "privilege_change" | "config_change";
export type NiveauAnomalie = "alerte" | "attention" | "info";

export interface LogEvent {
  horodatage: string;
  type: TypeEvenement;
  utilisateur?: string;
  source_ip?: string;
  ressource?: string;
}

export interface ParamsDetection {
  fenetre_minutes?: number;
  seuil_echecs?: number;
  heure_ouverture?: number;
  heure_fermeture?: number;
  seuil_ips_par_user?: number;
}

export interface Anomalie {
  code: string;
  niveau: NiveauAnomalie;
  titre: string;
  detail: string;
  entite: string;
  occurrences: number;
}

export interface AnalyseAnomalies {
  nb_events: number;
  nb_echecs_auth: number;
  nb_succes_auth: number;
  nb_ip_distinctes: number;
  nb_utilisateurs: number;
  periode_debut: string | null;
  periode_fin: string | null;
  niveau: NiveauAnomalie | "aucun";
  anomalies: Anomalie[];
  reference_cadre: string;
}

export interface CyberDetection {
  id: string;
  tenant_id: string;
  cible: string;
  nb_events: number;
  nb_anomalies: number;
  niveau: string;
  statut: "a_examiner" | "classee" | "traitee";
  params: ParamsDetection;
  resultat: AnalyseAnomalies;
  commentaire: string | null;
  country: string;
  created_at: string | null;
}

export const TYPE_EVENEMENT_LABELS: Record<TypeEvenement, string> = {
  auth_success: "Authentification réussie",
  auth_failure: "Échec d'authentification",
  access: "Accès",
  privilege_change: "Changement de privilège",
  config_change: "Changement de configuration",
};

export async function cyberAnomalies(body: { events: LogEvent[]; params?: ParamsDetection }): Promise<AnalyseAnomalies> {
  return api<AnalyseAnomalies>("/v1/cyber/anomalies", { body });
}

export async function createCyberDetection(body: { cible: string; events: LogEvent[]; params?: ParamsDetection }): Promise<CyberDetection> {
  return api<CyberDetection>("/v1/cyber/detections?tenant_id=local", { body });
}

export async function listCyberDetections(): Promise<{ detections: CyberDetection[] }> {
  return api<{ detections: CyberDetection[] }>("/v1/cyber/detections");
}

export async function getCyberDetection(id: string): Promise<CyberDetection> {
  return api<CyberDetection>(`/v1/cyber/detections/${id}`);
}

export async function decideCyberDetection(id: string, body: { statut: string; commentaire?: string }): Promise<CyberDetection> {
  return api<CyberDetection>(`/v1/cyber/detections/${id}/decision`, { body });
}

export async function deleteCyberDetection(id: string): Promise<{ status: string }> {
  return api<{ status: string }>(`/v1/cyber/detections/${id}`, { method: "DELETE" });
}
