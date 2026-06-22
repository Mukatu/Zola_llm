// Appels typés vers les moteurs déterministes ERP (/v1/erp/*).
import { api } from "./api";

export interface PayrollResult {
  brut_xaf: string;
  cotisations_salariales: Record<string, string>;
  total_cotisations_salariales_xaf: string;
  base_imposable_xaf: string;
  irpp_xaf: string;
  net_a_payer_xaf: string;
  cotisations_patronales: Record<string, string>;
  cout_employeur_xaf: string;
  "barème_validé": boolean;
}

export function payrollCompute(brut: string, allowUnvalidated: boolean): Promise<PayrollResult> {
  return api<PayrollResult>("/v1/erp/payroll/compute", {
    body: { brut_mensuel_xaf: brut, allow_unvalidated: allowUnvalidated },
  });
}

export function fmtXaf(v: string | number): string {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR") + " XAF" : String(v);
}
