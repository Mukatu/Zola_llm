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
