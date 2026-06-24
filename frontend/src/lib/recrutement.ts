// Client typé — SIRH Recrutement (/v1/erp/recruitment/*).
import { api } from "./api";

export const ETAPES = ["reçue", "présélection", "entretien", "offre", "embauché"] as const;

export interface Vacancy {
  id: string; code_vacance: string; code_emploi: string | null; intitule: string;
  statut: string; type_contrat_cible: string; date_ouverture: string; priorite: string; departement: string;
}
export interface Candidate { id: string; nom: string; prenom: string; source: string }
export interface Application {
  id: string; candidate_id: string; code_vacance: string; etape: string; date_candidature: string;
}
export interface RecruitmentDashboard {
  total_candidatures: number;
  par_etape: Record<string, number>;
  rejetes: number;
  embauches: number;
  taux_embauche_pct: string;
  time_to_hire_jours: string;
  par_source: Record<string, { candidatures: number; embauches: number }>;
  vacances_en_souffrance: { code_vacance: string; jours_ouverte: number; statut: string }[];
}

export function listVacancies(): Promise<{ vacancies: Vacancy[] }> { return api("/v1/erp/recruitment/vacancies"); }
export function createVacancy(b: { code_vacance: string; intitule: string; date_ouverture: string; code_emploi?: string; type_contrat_cible?: string; departement?: string }): Promise<Vacancy> {
  return api("/v1/erp/recruitment/vacancies", { body: b });
}
export function listCandidates(): Promise<{ candidates: Candidate[] }> { return api("/v1/erp/recruitment/candidates"); }
export function createCandidate(b: { nom: string; prenom?: string; source?: string }): Promise<Candidate> {
  return api("/v1/erp/recruitment/candidates", { body: b });
}
export function listApplications(): Promise<{ applications: Application[] }> { return api("/v1/erp/recruitment/applications"); }
export function createApplication(b: { candidate_id: string; code_vacance: string; date_candidature: string }): Promise<Application> {
  return api("/v1/erp/recruitment/applications", { body: b });
}
export function moveApplication(id: string, etape: string): Promise<Application> {
  return api(`/v1/erp/recruitment/applications/${id}`, { method: "PATCH", body: { etape } });
}
export function getRecruitmentDashboard(): Promise<RecruitmentDashboard> { return api("/v1/erp/recruitment/dashboard"); }
