// Client typé — Trésorerie persistée (/v1/erp/bank-accounts | cash-flows | treasury).
import { api } from "./api";
import { getToken } from "./auth";

export interface BankAccountRec {
  id: string;
  code: string;
  libelle: string;
  banque: string;
  type: string;
  devise: string;
  iban: string | null;
  solde_initial_xaf: string;
  solde_initial_devise: string | null;
  taux_applique: string | null;
}

export interface CashFlowRec {
  id: string;
  reference: string;
  compte_code: string;
  sens: string;
  montant_xaf: string;
  devise: string;
  montant_devise: string | null;
  taux_applique: string | null;
  date_operation: string | null;
  date_prevue: string | null;
  statut: string;
  niveau_validation: string;
  rapproche: boolean;
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
  solde_initial_devise?: string;
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
  montant_xaf?: string;
  devise?: string;
  montant_devise?: string;
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

// ----- Gouvernance & rapprochement (TRESO-3) -----
export function approveCashFlow(
  id: string,
): Promise<{ flow: CashFlowRec; execute: boolean; requiert_n2?: boolean }> {
  return api(`/v1/erp/cash-flows/${id}/approve`, { method: "POST", body: {} });
}

export interface ReleveLigne {
  date: string;
  montant_xaf: string;
  sens: string;
}
export interface ReconcileResult {
  rapprochements: { flux_id: string; releve_index: number; montant_xaf: number }[];
  flux_non_rapproches: string[];
  releve_non_rapproche: number[];
  taux_rapprochement_pct: string;
}
export function treasuryReconcile(releve: ReleveLigne[]): Promise<ReconcileResult> {
  return api("/v1/erp/treasury/reconcile", { body: { releve } });
}

// ----- Pilotage (TRESO-4) -----
export interface PeriodeForecast {
  libelle: string;
  debut: string;
  encaissements_xaf: number;
  decaissements_xaf: number;
  flux_net_xaf: number;
  solde_projete_xaf: number;
}
export interface Previsionnel {
  position_initiale_xaf: number;
  encaissements_total_xaf: number;
  decaissements_total_xaf: number;
  position_finale_xaf: number;
  decouvert_periode: string | null;
  decouvert_xaf: number | null;
  periodes: PeriodeForecast[];
}
export interface IndicateursTreso {
  encours_clients_xaf: number;
  encours_fournisseurs_xaf: number;
  dso_jours: number;
  dpo_jours: number;
  bfr_xaf: number;
  runway_mois: number | null;
}
export function treasuryPilotage(
  horizonJours = 90,
): Promise<{ previsionnel: Previsionnel; indicateurs: IndicateursTreso }> {
  return api(`/v1/erp/treasury/pilotage?horizon_jours=${horizonJours}`);
}
export async function downloadTreasuryPilotage(horizonJours = 90): Promise<void> {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const token = getToken();
  const r = await fetch(`${base}/v1/erp/treasury/pilotage/export?horizon_jours=${horizonJours}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "pilotage_tresorerie.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}
