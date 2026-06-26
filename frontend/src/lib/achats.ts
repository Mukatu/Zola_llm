// Client typé — Achats persisté (registre vivant) sur /v1/erp/suppliers|purchase-orders.
import { api } from "./api";

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
