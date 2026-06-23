// Client typé — SIRH Core HR & pilotage (/v1/erp/employees, /hr/*).
import { api } from "./api";

export interface EmployeeRec {
  id: string;
  matricule: string;
  nom_complet: string;
  genre: string;
  date_embauche: string;
  poste: string;
  departement: string;
  salaire_base_xaf: string;
  quotite: string;
  statut: string;
}

export interface EmployeeCreate {
  matricule: string;
  nom_complet: string;
  genre: string;
  date_embauche: string;
  poste: string;
  departement: string;
  salaire_base_xaf: string;
}

export interface HrDashboard {
  effectif: number;
  etp: string;
  masse_salariale_xaf: string;
  salaire_moyen_xaf: string;
  anciennete_moyenne_annees: string;
  turnover_pct: string;
  absenteisme_pct: string;
  ratio_encadrement_pct: string;
  ecart_salarial_hf_pct: string;
  repartition_genre: Record<string, number>;
  par_departement: Record<string, number>;
  par_type_contrat: Record<string, number>;
  pyramide_ages: Record<string, number>;
}

export interface HrEcheance {
  categorie: string;
  reference: string;
  libelle: string;
  date_cible: string;
  jours_restants: number;
  urgence: string;
}

export function listEmployees(): Promise<{ employees: EmployeeRec[] }> {
  return api("/v1/erp/employees");
}
export function createEmployee(b: EmployeeCreate): Promise<EmployeeRec> {
  return api("/v1/erp/employees", { body: b });
}
export function deleteEmployee(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/employees/${id}`, { method: "DELETE" });
}
export function getDashboard(): Promise<HrDashboard> {
  return api("/v1/erp/hr/dashboard");
}
export function getEcheancier(): Promise<{ echeances: HrEcheance[] }> {
  return api("/v1/erp/hr/echeancier");
}
