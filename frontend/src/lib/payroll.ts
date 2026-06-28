// Client typé — Paie historisée (/v1/erp/payslips | payroll/dashboard).
import { api } from "./api";

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
