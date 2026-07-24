// Client typé — Projets ONG : projets financés par bailleur + lignes budgétaires
// + suivi d'exécution + ventilation par bailleur (/v1/erp/projects|budget-lines).
import { api } from "./api";

export type StatutProjet = "en_cours" | "clos" | "suspendu";

export interface Project {
  id: string;
  tenant_id: string;
  intitule: string;
  bailleur: string;
  convention_ref: string | null;
  devise: string;
  budget_total: string;
  budget_total_devise: string | null;
  taux_applique: string | null;
  date_debut: string | null;
  date_fin: string | null;
  statut: StatutProjet;
  responsable: string | null;
  country: string;
  created_at: string;
  updated_at: string;
}

export interface BudgetLine {
  id: string;
  tenant_id: string;
  project_id: string;
  rubrique: string;
  activite: string | null;
  montant_prevu: string;
  montant_engage: string;
  montant_realise: string;
  eligible: boolean;
  created_at: string;
  updated_at: string;
}

export interface SuiviRubrique {
  rubrique: string;
  prevu: string;
  engage: string;
  realise: string;
  taux_execution: number;
  taux_engagement: number;
  depassement: boolean;
}

export interface SuiviTotaux {
  budget_total: string;
  total_prevu: string;
  total_engage: string;
  total_realise: string;
  taux_global: number;
  reste_a_realiser: string;
  realise_eligible: string;
  realise_total: string;
}

// Forme exacte renvoyée par GET /v1/erp/projects/{id}/suivi : le projet, le détail
// par rubrique, et les totaux regroupés sous "totaux" (pas à plat).
export interface Suivi {
  project: Project;
  par_rubrique: SuiviRubrique[];
  totaux: SuiviTotaux;
}

export type Ventilation = Record<
  string,
  { budget_total: string; realise: string; taux: number }
>;

export function listProjects(): Promise<{ projects: Project[] }> {
  return api("/v1/erp/projects");
}
export function createProject(b: {
  intitule: string;
  bailleur: string;
  convention_ref?: string | null;
  devise?: string;
  budget_total?: string;
  budget_total_devise?: string;
  date_debut?: string | null;
  date_fin?: string | null;
  statut?: StatutProjet;
  responsable?: string | null;
}): Promise<Project> {
  return api("/v1/erp/projects", { body: b });
}
export function updateProject(id: string, patch: Partial<Project>): Promise<Project> {
  return api(`/v1/erp/projects/${id}`, { method: "PATCH", body: patch });
}
export function deleteProject(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/projects/${id}`, { method: "DELETE" });
}

export function listBudgetLines(projectId: string): Promise<{ budget_lines: BudgetLine[] }> {
  return api(`/v1/erp/budget-lines?project_id=${projectId}`);
}
export function createBudgetLine(b: {
  project_id: string;
  rubrique: string;
  activite?: string | null;
  montant_prevu: string;
  montant_engage?: string;
  montant_realise?: string;
  eligible?: boolean;
}): Promise<BudgetLine> {
  return api("/v1/erp/budget-lines", { body: b });
}
export function updateBudgetLine(id: string, patch: Partial<BudgetLine>): Promise<BudgetLine> {
  return api(`/v1/erp/budget-lines/${id}`, { method: "PATCH", body: patch });
}
export function deleteBudgetLine(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/budget-lines/${id}`, { method: "DELETE" });
}

export function getSuivi(projectId: string): Promise<Suivi> {
  return api(`/v1/erp/projects/${projectId}/suivi`);
}
export function getVentilation(): Promise<Ventilation> {
  return api("/v1/erp/projects/ventilation");
}
