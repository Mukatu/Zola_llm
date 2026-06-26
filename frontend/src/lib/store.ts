// Client typé — système de référence léger (Factures) + clôture continue.
import { api } from "./api";

export interface InvoiceRec {
  id: string;
  numero: string;
  sens: string;
  tiers: string;
  date_emission: string;
  date_echeance: string | null;
  montant_ht_xaf: string;
  montant_ttc_xaf: string;
  payee: boolean;
  devise: string;
}

export interface InvoiceCreate {
  numero: string;
  tiers: string;
  date_emission: string;
  montant_ht_xaf: string;
  montant_ttc_xaf: string;
  sens?: string;
}

export interface TxInput {
  id_externe: string;
  date_operation: string;
  libelle: string;
  montant_xaf: string;
  sens: string;
}

export interface Cloture {
  total_factures: number;
  lettrees: number;
  en_attente: number;
  taux_lettrage_pct: string;
  montant_lettre_xaf: string;
  encours_clients_xaf: string;
}

export interface ReconcileResult {
  rapprochements: { invoice_id: string; transaction_id: string; montant_xaf: string }[];
  factures_en_attente: { invoice_id: string; numero: string; tiers: string; montant_ttc_xaf: string }[];
  mouvements_non_rapproches: string[];
  cloture: Cloture | null;
}

export function listInvoices(): Promise<{ invoices: InvoiceRec[] }> {
  return api("/v1/erp/invoices");
}
export function createInvoice(b: InvoiceCreate): Promise<InvoiceRec> {
  return api("/v1/erp/invoices", { body: b });
}
export function payInvoice(id: string): Promise<InvoiceRec> {
  return api(`/v1/erp/invoices/${id}/pay`, { method: "POST", body: {} });
}
export function deleteInvoice(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/invoices/${id}`, { method: "DELETE" });
}
export function reconcile(transactions: TxInput[]): Promise<ReconcileResult> {
  return api("/v1/erp/reconcile", { body: { transactions } });
}

// ----- Écritures comptables (balance vivante) -----
export interface JournalLineIn {
  compte: string;
  libelle: string;
  debit_xaf: string;
  credit_xaf: string;
}
export interface EntryRec {
  id: string;
  date_ecriture: string;
  journal: string;
  libelle: string;
  total_debit_xaf: string;
  total_credit_xaf: string;
  equilibre: boolean;
}
export interface BalanceLine {
  compte: string;
  debit_xaf: string;
  credit_xaf: string;
  solde_xaf: string;
}
export interface Balance {
  comptes: BalanceLine[];
  total_debit_xaf: string;
  total_credit_xaf: string;
  equilibre: boolean;
}

export function createEntry(body: {
  date_ecriture: string;
  journal: string;
  libelle: string;
  lignes: JournalLineIn[];
}): Promise<EntryRec> {
  return api("/v1/erp/journal", { body });
}
export function listEntries(): Promise<{ entries: EntryRec[] }> {
  return api("/v1/erp/journal");
}
export function getBalance(): Promise<Balance> {
  return api("/v1/erp/journal/balance");
}
export function deleteEntry(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/journal/${id}`, { method: "DELETE" });
}

// ----- Stock persistant -----
export interface StockRec {
  id: string;
  sku: string;
  libelle: string;
  quantite_actuelle: string;
  unite?: string;
  conso_moyenne_jour: string;
  delai_appro_jours: number;
  stock_securite: string;
  pmp_xaf?: string;
  valeur_stock_xaf?: string;
}

export interface StockMoveRec {
  id: string;
  reference: string;
  type: string;
  sku: string;
  quantite: string;
  cout_unitaire_xaf: string | null;
  valeur_xaf: string;
  emplacement: string | null;
  emplacement_dest: string | null;
  lot: string | null;
  date_peremption: string | null;
  statut: string;
  motif: string;
  date_mouvement: string | null;
}
export interface ReapproSugg {
  sku: string;
  libelle: string;
  quantite_a_commander: string;
  jours_avant_rupture: string | null;
  urgence: string;
}
export function listStock(): Promise<{ items: StockRec[] }> {
  return api("/v1/erp/stock");
}
export function createStock(body: {
  sku: string;
  libelle: string;
  quantite_actuelle: string;
  conso_moyenne_jour: string;
  delai_appro_jours: number;
  stock_securite: string;
}): Promise<StockRec> {
  return api("/v1/erp/stock", { body });
}
export function deleteStock(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/stock/${id}`, { method: "DELETE" });
}
export function analyzeStock(): Promise<{ suggestions: ReapproSugg[]; alertes: ReapproSugg[] }> {
  return api("/v1/erp/stock/analyze", { method: "POST", body: {} });
}

// ----- Mouvements de stock (grand-livre valorisé) -----
export function listStockMoves(sku?: string): Promise<{ moves: StockMoveRec[] }> {
  const qs = sku ? `?sku=${encodeURIComponent(sku)}` : "";
  return api(`/v1/erp/stock-moves${qs}`);
}
export function createStockMove(b: {
  reference: string;
  type: string;
  sku: string;
  quantite: string;
  cout_unitaire_xaf?: string | null;
  motif?: string;
  date_mouvement: string;
}): Promise<StockMoveRec> {
  return api("/v1/erp/stock-moves", { body: b });
}
export function validateStockMove(id: string): Promise<{ move: StockMoveRec; article: StockRec }> {
  return api(`/v1/erp/stock-moves/${id}/validate`, { method: "POST", body: {} });
}
export function deleteStockMove(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/stock-moves/${id}`, { method: "DELETE" });
}
