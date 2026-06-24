// Client typé — SIRH Formation (/v1/erp/formation/*).
import { api } from "./api";

export interface Training { id: string; code: string; intitule: string; duree_heures: string; cout_xaf: string; competences_visees: string[] }
export interface Session { id: string; training_code: string; date_debut: string; statut: string; lieu: string }
export interface Enrollment { id: string; session_id: string; employee_matricule: string; statut: string }
export interface FormationDashboard {
  nb_formations: number; nb_sessions: number; nb_inscriptions: number; nb_realisees: number;
  taux_realisation_pct: string; cout_total_xaf: string; cout_par_employe_xaf: string;
  heures_par_employe: string; satisfaction_moyenne: string; efficacite_moyenne: string;
  competences_visees: string[];
}

export function listTrainings(): Promise<{ trainings: Training[] }> { return api("/v1/erp/formation/trainings"); }
export function createTraining(b: { code: string; intitule: string; duree_heures: string; cout_xaf: string }): Promise<Training> {
  return api("/v1/erp/formation/trainings", { body: b });
}
export function listSessions(): Promise<{ sessions: Session[] }> { return api("/v1/erp/formation/sessions"); }
export function createSession(b: { training_code: string; date_debut: string; lieu?: string }): Promise<Session> {
  return api("/v1/erp/formation/sessions", { body: b });
}
export function listEnrollments(): Promise<{ enrollments: Enrollment[] }> { return api("/v1/erp/formation/enrollments"); }
export function createEnrollment(b: { session_id: string; employee_matricule: string }): Promise<Enrollment> {
  return api("/v1/erp/formation/enrollments", { body: b });
}
export function patchEnrollment(id: string, statut: string): Promise<Enrollment> {
  return api(`/v1/erp/formation/enrollments/${id}`, { method: "PATCH", body: { statut } });
}
export function getFormationDashboard(): Promise<FormationDashboard> { return api("/v1/erp/formation/dashboard"); }
