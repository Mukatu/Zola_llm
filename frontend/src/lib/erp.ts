// Appels typés vers les moteurs déterministes ERP (/v1/erp/*).
import { api } from "./api";

export function fmtXaf(v: string | number): string {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR") + " XAF" : String(v);
}

// ----- Paie -----
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
  return api<PayrollResult>("/v1/erp/payroll/compute", { body: { brut_mensuel_xaf: brut, allow_unvalidated: allowUnvalidated } });
}

// ----- Compta -----
export interface JournalLineInput { compte: string; libelle: string; debit_xaf: string; credit_xaf: string }
export interface ValidationReport {
  ok: boolean; total_debit_xaf: string; total_credit_xaf: string; errors: string[]; warnings: string[];
}
export function comptaValidate(lignes: JournalLineInput[]): Promise<ValidationReport> {
  return api<ValidationReport>("/v1/erp/compta/validate", {
    body: { date_ecriture: new Date().toISOString().slice(0, 10), journal: "OD", libelle: "Saisie", lignes },
  });
}

// ----- Supply -----
export interface StockItemInput {
  sku: string; libelle: string; quantite_actuelle: string; conso_moyenne_jour: string;
  delai_appro_jours: number; stock_securite: string;
}
export interface ReapproSuggestion {
  sku: string; libelle: string; quantite_actuelle: string; point_de_commande: string;
  quantite_a_commander: string; jours_avant_rupture: string | null; urgence: string;
}
export function supplyAnalyze(items: StockItemInput[]): Promise<{ suggestions: ReapproSuggestion[]; alertes: ReapproSuggestion[] }> {
  return api("/v1/erp/supply/analyze", { body: { items } });
}

// ----- Achats -----
export interface OffreInput { id_externe: string; fournisseur: string; objet: string; montant_ttc_xaf: string; montant_ht_xaf: string; delai_livraison_jours: number }
export interface ComparatifLigne { offre_id: string; fournisseur: string; montant_ttc_xaf: string; delai_livraison_jours: number; score: number; rang: number }
export function achatsCompare(offres: OffreInput[]): Promise<{ classement: ComparatifLigne[] }> {
  return api("/v1/erp/achats/compare", { body: { offres } });
}

// ----- Facility -----
export interface AssetInput { id_externe: string; libelle: string; maintenance_intervalle_jours: number; derniere_maintenance: string | null }
export interface EcheanceInput { id_externe: string; type_echeance: string; libelle: string; date_echeance: string }
export interface FacilityAlerte { categorie: string; reference: string; libelle: string; date_cible: string; jours_restants: number; urgence: string }
export function facilityEcheancier(assets: AssetInput[], echeances: EcheanceInput[]): Promise<{ maintenances: FacilityAlerte[]; echeances: FacilityAlerte[] }> {
  return api("/v1/erp/facility/echeancier", { body: { assets, echeances } });
}

// ----- HSE -----
export interface RisqueInput { id_externe: string; libelle: string; probabilite: number; gravite: number }
export interface RisqueEvalue { reference: string; libelle: string; criticite: number; niveau: string }
export function hseCartographie(risques: RisqueInput[]): Promise<{ risques: RisqueEvalue[] }> {
  return api("/v1/erp/hse/cartographie", { body: { risques } });
}
