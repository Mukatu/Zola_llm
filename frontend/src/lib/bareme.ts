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
export interface Rubrique {
  code: string;
  libelle: string;
  type: "gain" | "retenue";
  mode: "fixe" | "pct_brut";
  valeur: string;
  imposable: boolean;
  soumis_cnss: boolean;
  applicable_a_tous: boolean;
}
export interface PalierAnciennete {
  annees: number;
  taux: string;
}
export interface PrimeAnciennete {
  actif: boolean;
  paliers: PalierAnciennete[];
}
export interface Bareme {
  country: string;
  version: string;
  source: string;
  source_donnees: "tenant" | "defaut";
  editable: boolean;
  valide_fichier: boolean;
  effectivement_valide: boolean;
  validation: BaremeValidation;
  smig_xaf: string;
  abattement_irpp_taux: string;
  plafond_parts: string;
  impot_minimum_annuel_xaf: string;
  heures_mensuelles: string;
  regime_its_depuis_annee: number;
  regimes: Record<string, BaremeRegime>;
  cnss_branches: CnssBranche[];
  rubriques: Rubrique[];
  prime_anciennete: PrimeAnciennete;
  autres_charges_a_confirmer: Record<string, unknown>[];
  sources: BaremeSource[];
}

export interface BaremeEdit {
  smig_xaf?: string;
  abattement_irpp_taux?: string;
  plafond_parts?: string;
  impot_minimum_annuel_xaf?: string;
  regime_its_depuis_annee?: number;
  regimes?: Record<string, BaremeRegime>;
  cnss_branches?: CnssBranche[];
  rubriques?: Rubrique[];
  prime_anciennete?: PrimeAnciennete;
  edited_by?: string;
}

export function getBareme(country = "cg"): Promise<Bareme> {
  return api(`/v1/erp/payroll/bareme?country=${encodeURIComponent(country)}`);
}
export function editBareme(b: BaremeEdit, country = "cg"): Promise<Bareme> {
  return api(`/v1/erp/payroll/bareme?country=${encodeURIComponent(country)}`, {
    method: "PUT",
    body: b,
  });
}
export function validateBareme(
  b: { validated: boolean; validated_by?: string; note?: string },
  country = "cg",
): Promise<Bareme> {
  return api(`/v1/erp/payroll/bareme/validate?country=${encodeURIComponent(country)}`, { body: b });
}

// ----- Affectation des rubriques par salarié (PAIE-6c) -----
export interface RubriqueAffectation {
  employee_matricule: string;
  code: string;
  valeur: string | null;
}
export interface CatalogueRubrique {
  code: string;
  libelle: string;
  type: "gain" | "retenue";
  applicable_a_tous: boolean;
  valeur: string;
  mode: "fixe" | "pct_brut";
}
export interface EmployeeRubriques {
  matricule: string;
  affectations: RubriqueAffectation[];
  catalogue: CatalogueRubrique[];
}
export function getEmployeeRubriques(matricule: string): Promise<EmployeeRubriques> {
  return api(`/v1/erp/employees/${encodeURIComponent(matricule)}/rubriques`);
}
export function setEmployeeRubrique(
  matricule: string,
  code: string,
  valeur?: string | null,
): Promise<RubriqueAffectation> {
  return api(`/v1/erp/employees/${encodeURIComponent(matricule)}/rubriques/${code}`, {
    method: "PUT",
    body: { valeur: valeur ?? null },
  });
}
export function deleteEmployeeRubrique(
  matricule: string,
  code: string,
): Promise<{ deleted: string }> {
  return api(`/v1/erp/employees/${encodeURIComponent(matricule)}/rubriques/${code}`, {
    method: "DELETE",
  });
}
