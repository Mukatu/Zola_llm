// Client typé — Achats persisté (registre vivant) sur /v1/erp/suppliers|purchase-orders.
import { api } from "./api";
import { getToken } from "./auth";

export interface SupplierRec {
  id: string;
  id_externe: string;
  nom: string;
  secteur: string | null;
  note_qualite: string;
  delai_moyen_jours: number;
  documents_conformite: string[];
  actif: boolean;
  country: string;
}

export interface SupplierScore {
  id: string;
  id_externe: string;
  nom: string;
  score: number;
  grade: string;
  raisons: string[];
  conformite_manquante: string[];
}

export interface PurchaseOrderLine {
  libelle: string;
  montant_ht_xaf: string;
}
export interface PurchaseOrderRec {
  id: string;
  id_externe: string;
  numero: string;
  fournisseur: string;
  objet: string;
  date_emission: string | null;
  statut: string;
  lignes: PurchaseOrderLine[];
  montant_ht_xaf: string;
  montant_ttc_xaf: string;
  delai_livraison_jours: number;
  invoice_id: string | null;
  country: string;
}

export interface ComparatifLigne {
  offre_id: string;
  fournisseur: string;
  montant_ttc_xaf: string;
  delai_livraison_jours: number;
  score: number;
  rang: number;
}

// ----- Fournisseurs -----
export function listSuppliers(): Promise<{ suppliers: SupplierRec[] }> {
  return api("/v1/erp/suppliers");
}
export function createSupplier(b: {
  id_externe: string;
  nom: string;
  secteur?: string;
  note_qualite?: string;
  delai_moyen_jours?: number;
  documents_conformite?: string[];
}): Promise<SupplierRec> {
  return api("/v1/erp/suppliers", { body: b });
}
export function supplierScores(): Promise<{ scores: SupplierScore[] }> {
  return api("/v1/erp/suppliers/scores");
}
export function deleteSupplier(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/suppliers/${id}`, { method: "DELETE" });
}

// ----- Bons de commande -----
export function listPurchaseOrders(): Promise<{ purchase_orders: PurchaseOrderRec[] }> {
  return api("/v1/erp/purchase-orders");
}
export function createPurchaseOrder(b: {
  id_externe: string;
  numero: string;
  fournisseur: string;
  objet?: string;
  date_emission: string;
  statut?: string;
  montant_ht_xaf: string;
  montant_ttc_xaf: string;
  delai_livraison_jours?: number;
}): Promise<PurchaseOrderRec> {
  return api("/v1/erp/purchase-orders", { body: b });
}
export function comparePurchaseOrders(objet?: string): Promise<{ classement: ComparatifLigne[] }> {
  const qs = objet ? `?objet=${encodeURIComponent(objet)}` : "";
  return api(`/v1/erp/purchase-orders/compare${qs}`);
}
export function receiptPurchaseOrder(
  id: string,
): Promise<{ purchase_order: PurchaseOrderRec; invoice: { numero: string } }> {
  return api(`/v1/erp/purchase-orders/${id}/receipt`, { method: "POST", body: {} });
}
export function deletePurchaseOrder(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/purchase-orders/${id}`, { method: "DELETE" });
}

// ----- Engagements (chaîne EB → DA → BC) -----
export interface EngagementRec {
  id: string;
  numero_eb: string;
  numero_da: string | null;
  numero_bc: string | null;
  date_eb: string | null;
  date_da: string | null;
  date_bc: string | null;
  direction: string | null;
  service: string | null;
  demandeur: string | null;
  acheteur: string | null;
  fournisseur: string | null;
  estimation_xaf: string;
  montant_xaf: string;
  statut_ebda: string;
  statut_bc: string;
}

export interface DimensionLigne {
  cle: string;
  nb: number;
  engage_xaf: number;
  estimation_xaf: number;
}
export interface EngagementStats {
  nb_total: number;
  par_phase: Record<string, number>;
  nb_eb: number;
  nb_da: number;
  nb_bc: number;
  taux_eb_vers_da_pct: number;
  taux_da_vers_bc_pct: number;
  taux_eb_vers_bc_pct: number;
  estimation_totale_xaf: number;
  engage_total_xaf: number;
  ecart_xaf: number;
  nb_depassements: number;
  par_direction: DimensionLigne[];
  par_acheteur: DimensionLigne[];
  funnel_statut_bc: Record<string, number>;
  delai_moyen_eb_da_jours: number | null;
  delai_moyen_da_bc_jours: number | null;
}
export interface EngagementAlerte {
  type: string;
  reference: string;
  libelle: string;
  priorite: string;
}

export function listEngagements(): Promise<{ engagements: EngagementRec[] }> {
  return api("/v1/erp/engagements");
}
export function createEngagement(b: {
  numero_eb: string;
  numero_da?: string;
  numero_bc?: string;
  date_eb?: string;
  date_da?: string;
  date_bc?: string;
  direction?: string;
  service?: string;
  demandeur?: string;
  acheteur?: string;
  fournisseur?: string;
  estimation_xaf?: string;
  montant_xaf?: string;
  statut_ebda?: string;
  statut_bc?: string;
}): Promise<EngagementRec> {
  return api("/v1/erp/engagements", { body: b });
}
export function engagementStats(): Promise<{ stats: EngagementStats; alertes: EngagementAlerte[] }> {
  return api("/v1/erp/engagements/stats");
}

// ----- Pilotage budgétaire (CDG) -----
export interface PurchaseBudgetRec {
  id: string;
  direction: string;
  exercice: string;
  budget_xaf: string;
}
export interface PilotageDirection {
  direction: string;
  budget_xaf: number;
  engage_xaf: number;
  reste_xaf: number;
  consommation_pct: number;
  niveau: string; // ok | vigilance | depassement | hors_budget
  nb: number;
}
export interface SerieMensuelle {
  mois: string;
  engage_xaf: number;
}
export interface FournisseurEngage {
  fournisseur: string;
  engage_xaf: number;
  nb: number;
}
export interface PilotageBudgetaire {
  budget_total_xaf: number;
  engage_total_xaf: number;
  reste_total_xaf: number;
  consommation_pct: number;
  par_direction: PilotageDirection[];
  serie_mensuelle: SerieMensuelle[];
  top_fournisseurs: FournisseurEngage[];
}

export function listPurchaseBudgets(exercice?: string): Promise<{ budgets: PurchaseBudgetRec[] }> {
  const qs = exercice ? `?exercice=${encodeURIComponent(exercice)}` : "";
  return api(`/v1/erp/purchase-budgets${qs}`);
}
export function setPurchaseBudget(b: {
  direction: string;
  exercice: string;
  budget_xaf: string;
}): Promise<PurchaseBudgetRec> {
  return api("/v1/erp/purchase-budgets", { body: b });
}
export function engagementPilotage(
  exercice?: string,
): Promise<{ exercice: string | null; pilotage: PilotageBudgetaire }> {
  const qs = exercice ? `?exercice=${encodeURIComponent(exercice)}` : "";
  return api(`/v1/erp/engagements/pilotage${qs}`);
}

// Télécharge le classeur CDG (engagé vs budget) en portant le token d'auth.
export async function downloadPilotage(exercice?: string): Promise<void> {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const token = getToken();
  const qs = exercice ? `?exercice=${encodeURIComponent(exercice)}` : "";
  const r = await fetch(`${base}/v1/erp/engagements/pilotage/export${qs}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `pilotage_achats_${exercice ?? "tous"}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}
