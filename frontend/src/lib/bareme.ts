// Client typé — barème de paie : valeurs sourcées + validation experte (PAIE-5).
import { api } from "./api";

export interface BaremeTranche {
  plafond_xaf: string | null;
  taux: string;
}
export interface BaremeRegime {
  label: string;
  bareme: BaremeTranche[];
}
export interface CnssBranche {
  nom: string;
  label: string;
  taux_salarie: string;
  taux_employeur: string;
  plafond_mensuel_xaf: string | null;
}
export interface BaremeSource {
  id?: string;
  url: string;
  label: string;
  confiance: string;
  couvre?: string[];
}
export interface BaremeValidation {
  validated: boolean;
  validated_by: string;
  note: string;
  validated_at: string | null;
}
export interface Bareme {
  country: string;
  version: string;
  source: string;
  valide_fichier: boolean;
  effectivement_valide: boolean;
  validation: BaremeValidation;
  smig_xaf: string;
  abattement_irpp_taux: string;
  plafond_parts: string;
  regime_its_depuis_annee: number;
  regimes: Record<string, BaremeRegime>;
  cnss_branches: CnssBranche[];
  autres_charges_a_confirmer: Record<string, unknown>[];
  sources: BaremeSource[];
}

export function getBareme(country = "cg"): Promise<Bareme> {
  return api(`/v1/erp/payroll/bareme?country=${encodeURIComponent(country)}`);
}
export function validateBareme(
  b: { validated: boolean; validated_by?: string; note?: string },
  country = "cg",
): Promise<Bareme> {
  return api(`/v1/erp/payroll/bareme/validate?country=${encodeURIComponent(country)}`, { body: b });
}
