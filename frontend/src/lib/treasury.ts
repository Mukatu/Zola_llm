// Client typé — Trésorerie persistée (/v1/erp/bank-accounts | cash-flows | treasury).
import { api } from "./api";

export interface BankAccountRec {
  id: string;
  code: string;
  libelle: string;
  banque: string;
  type: string;
  devise: string;
  iban: string | null;
  solde_initial_xaf: string;
}

export interface CashFlowRec {
  id: string;
  reference: string;
  compte_code: string;
  sens: string;
  montant_xaf: string;
  date_operation: string | null;
  date_prevue: string | null;
  statut: string;
  categorie: string;
  tiers: string;
  libelle: string;
  mode: string;
  invoice_id: string | null;
}

export interface CompteLigne {
  code: string;
  libelle: string;
  type: string;
  devise: string;
  solde_initial_xaf: number;
  encaisse_xaf: number;
  decaisse_xaf: number;
  solde_realise_xaf: number;
  encaisse_prevu_xaf: number;
  decaisse_prevu_xaf: number;
  solde_projete_xaf: number;
}
export interface PositionTresorerie {
  nb_comptes: number;
  total_realise_xaf: number;
  total_projete_xaf: number;
  par_devise: Record<string, string>;
  par_compte: CompteLigne[];
}

// ----- Comptes -----
export function listBankAccounts(): Promise<{ accounts: BankAccountRec[] }> {
  return api("/v1/erp/bank-accounts");
}
export function createBankAccount(b: {
  code: string;
  libelle: string;
  banque?: string;
  type?: string;
  devise?: string;
  solde_initial_xaf?: string;
}): Promise<BankAccountRec> {
  return api("/v1/erp/bank-accounts", { body: b });
}
export function deleteBankAccount(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/bank-accounts/${id}`, { method: "DELETE" });
}

// ----- Flux -----
export function listCashFlows(params?: {
  compte_code?: string;
  statut?: string;
}): Promise<{ flows: CashFlowRec[] }> {
  const q = new URLSearchParams();
  if (params?.compte_code) q.set("compte_code", params.compte_code);
  if (params?.statut) q.set("statut", params.statut);
  const qs = q.toString();
  return api(`/v1/erp/cash-flows${qs ? `?${qs}` : ""}`);
}
export function createCashFlow(b: {
  reference: string;
  compte_code: string;
  sens: string;
  montant_xaf: string;
  date_operation: string;
  date_prevue?: string | null;
  statut?: string;
  categorie?: string;
  tiers?: string;
  libelle?: string;
}): Promise<CashFlowRec> {
  return api("/v1/erp/cash-flows", { body: b });
}
export function deleteCashFlow(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/cash-flows/${id}`, { method: "DELETE" });
}

// ----- Position -----
export function treasuryPosition(): Promise<{ position: PositionTresorerie }> {
  return api("/v1/erp/treasury/position");
}
