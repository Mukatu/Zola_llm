// Client typé — SIRH Référentiels (RME/RMC) + matrice + GPEC.
import { api } from "./api";

export interface JobRole {
  id: string; code_emploi: string; famille_professionnelle: string;
  intitule: string; mission_principale: string; activites: string[]; kpis: string[];
}
export interface Skill {
  id: string; code_competence: string; domaine: string; intitule: string;
  niveau_1: string; niveau_2: string; niveau_3: string; niveau_4: string;
}
export interface MatrixLine {
  matricule: string; nom_complet: string; code_emploi: string | null; notes: Record<string, number>;
}
export interface Matrix { competences: string[]; lignes: MatrixLine[] }
export interface GpecEmploye {
  matricule: string; nom_complet: string; code_emploi: string | null; couverture_pct: string;
  ecarts: { code_competence: string; niveau_requis: number; niveau_detenu: number; ecart: number }[];
}
export interface Gpec {
  par_employe: GpecEmploye[];
  experts_par_competence: Record<string, number>;
  competences_critiques: { code_competence: string; experts: number; requise_par_emplois: number }[];
}

export function listJobRoles(): Promise<{ job_roles: JobRole[] }> { return api("/v1/erp/hr/job-roles"); }
export function createJobRole(b: Partial<JobRole>): Promise<JobRole> { return api("/v1/erp/hr/job-roles", { body: b }); }
export function listSkills(): Promise<{ skills: Skill[] }> { return api("/v1/erp/hr/skills"); }
export function createSkill(b: Partial<Skill>): Promise<Skill> { return api("/v1/erp/hr/skills", { body: b }); }
export function createRoleSkill(b: { code_emploi: string; code_competence: string; niveau_requis: number }): Promise<unknown> {
  return api("/v1/erp/hr/role-skills", { body: b });
}
export function setEmployeeSkill(b: { employee_matricule: string; code_competence: string; note: number }): Promise<unknown> {
  return api("/v1/erp/hr/employee-skills", { body: b });
}
export function getMatrix(): Promise<Matrix> { return api("/v1/erp/hr/matrix"); }
export function getGpec(): Promise<Gpec> { return api("/v1/erp/hr/gpec"); }
