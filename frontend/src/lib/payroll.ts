// Client typé — Paie historisée (/v1/erp/payslips | payroll/dashboard | DAS 1).
import { api } from "./api";
import { getToken } from "./auth";

export interface PayslipRec {
  id: string;
  employee_matricule: string;
  periode: string;
  brut_xaf: string;
  total_cotisations_salariales_xaf: string;
  base_imposable_xaf: string;
  irpp_xaf: string;
  net_a_payer_xaf: string;
  cout_employeur_xaf: string;
  statut: string;
  date_paiement: string | null;
}

export interface PayrollDashboard {
  periode: string | null;
  nb_bulletins: number;
  masse_salariale_brute_xaf: string;
  total_net_a_payer_xaf: string;
  total_irpp_xaf: string;
  total_cotisations_salariales_xaf: string;
  total_cotisations_patronales_xaf: string;
  cout_employeur_total_xaf: string;
}

export function createPayslip(b: {
  employee_matricule: string;
  periode: string;
  brut_mensuel_xaf: string;
  avantages_nature_xaf?: string;
  indemnites_non_imposables_xaf?: string;
  allow_unvalidated?: boolean;
}): Promise<PayslipRec> {
  return api("/v1/erp/payslips", { body: b });
}
export function listPayslips(periode?: string): Promise<{ payslips: PayslipRec[] }> {
  const qs = periode ? `?periode=${encodeURIComponent(periode)}` : "";
  return api(`/v1/erp/payslips${qs}`);
}
export function patchPayslip(
  id: string,
  b: { statut?: string; date_paiement?: string },
): Promise<PayslipRec> {
  return api(`/v1/erp/payslips/${id}`, { method: "PATCH", body: b });
}
export function deletePayslip(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/payslips/${id}`, { method: "DELETE" });
}
export function payrollDashboard(periode?: string): Promise<PayrollDashboard> {
  const qs = periode ? `?periode=${encodeURIComponent(periode)}` : "";
  return api(`/v1/erp/payroll/dashboard${qs}`);
}

// ----- Bulletin imprimable + modèle (PAIE-7a) -----
export interface BulletinModele {
  titre: string;
  logo_texte: string;
  couleur: string;
  mentions: string;
  afficher_cotisations_patronales: boolean;
  afficher_cout_employeur: boolean;
  devise: string;
}
export function getBulletinModele(): Promise<BulletinModele> {
  return api("/v1/erp/payroll/bulletin-modele");
}
export function saveBulletinModele(b: BulletinModele): Promise<BulletinModele> {
  return api("/v1/erp/payroll/bulletin-modele", { method: "PUT", body: b });
}
export async function downloadBulletin(payslipId: string, label: string): Promise<void> {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const token = getToken();
  const r = await fetch(`${base}/v1/erp/payslips/${payslipId}/bulletin`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `bulletin_${label}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

// ----- DAS 1 / état annuel (PAIE-3) -----
export interface EtatAnnuelLigne {
  matricule: string;
  nom: string;
  mensuels_xaf: string[];
  total_xaf: string;
  irpp_annuel_xaf: string;
}
export interface EtatAnnuel {
  exercice: string;
  mois: string[];
  lignes: EtatAnnuelLigne[];
  total_brut_xaf: string;
  total_irpp_xaf: string;
}
export interface Das1Ligne {
  matricule: string;
  nom: string;
  sexe: string;
  profession: string;
  date_embauche: string | null;
  date_depart: string | null;
  brut_annuel_xaf: number;
  salaire_plafonne_xaf: number;
  base_imposable_xaf: number;
  irpp_xaf: number;
  avantages_nature_xaf: number;
  indemnites_non_imposables_xaf: number;
  taxe_regionale_xaf: number;
  tol_camu_xaf: number;
}
export interface Das1 {
  exercice: string;
  employeur: Record<string, string>;
  nb_salaries: number;
  totaux: {
    brut_xaf: string;
    plafonne_xaf: string;
    base_imposable_xaf: string;
    irpp_xaf: string;
    avantages_nature_xaf: string;
    indemnites_non_imposables_xaf: string;
    taxe_regionale_xaf: string;
    tol_camu_xaf: string;
  };
  lignes: Das1Ligne[];
}

export function payrollEtatAnnuel(annee: string): Promise<EtatAnnuel> {
  return api(`/v1/erp/payroll/etat-annuel?annee=${encodeURIComponent(annee)}`);
}
export function payrollDas1(annee: string): Promise<Das1> {
  return api(`/v1/erp/payroll/das1?annee=${encodeURIComponent(annee)}`);
}
export async function downloadDas1(annee: string): Promise<void> {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const token = getToken();
  const r = await fetch(`${base}/v1/erp/payroll/das1/export?annee=${encodeURIComponent(annee)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `DAS1_${annee}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}
