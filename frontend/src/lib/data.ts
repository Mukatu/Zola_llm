// Clients typés — vague data (CRM / BI / Finance) sur /v1/*.
import { api } from "./api";

// ----- CRM -----
export interface OppInput {
  id_externe: string; client: string; libelle: string; montant_xaf: string; etape: string;
  derniere_interaction?: string | null;
}
export interface PipelineStats {
  nb_open: number; total_open_xaf: string; weighted_open_xaf: string; win_rate_pct: string;
  par_etape_xaf: Record<string, string>;
}
export interface LeadScore { score: number; grade: string; raisons: string[] }
export interface RelanceItem { type: string; reference: string; libelle: string; priorite: string }
export interface CrmResult { pipeline: PipelineStats; scores: Record<string, LeadScore>; relances: RelanceItem[] }
export function crmAnalyze(opportunities: OppInput[], quotes: unknown[] = []): Promise<CrmResult> {
  return api<CrmResult>("/v1/crm/analyze", { body: { opportunities, quotes } });
}

// ----- BI -----
export interface Kpi { code: string; libelle: string; valeur: string; unite: string; domaine: string; periode: string | null }
export function biKpis(payload: { invoices?: unknown[]; transactions?: unknown[]; employees?: unknown[]; periode?: string }): Promise<{ kpis: Kpi[] }> {
  return api("/v1/bi/kpis", { body: payload });
}
// Cockpit transversal agrégé sur le registre vivant (store).
export function biDashboard(): Promise<{ kpis: Kpi[] }> {
  return api("/v1/bi/dashboard");
}
// Cockpit v2 : KPIs + signaux déterministes + échéances indicatives.
export interface Signal { code: string; niveau: string; domaine: string; titre: string; detail: string; kpi_code: string | null }
export interface Echeance { code: string; libelle: string; periodicite: string; date_limite: string; jours_restants: number; indicatif: boolean; note: string }
export interface Cockpit { generated_at: string; kpis: Kpi[]; signals: Signal[]; echeances: Echeance[] }
export function biCockpit(): Promise<Cockpit> {
  return api("/v1/bi/cockpit");
}
export function biBrief(): Promise<{ brief: string; signals_apercu: string }> {
  return api("/v1/bi/brief", { body: {} });
}
export function biAsk(question: string): Promise<{ answer: string }> {
  return api("/v1/bi/ask", { body: { question } });
}

// ----- Finance -----
export interface FinanceFinding { type: string; severity: string; libelle: string; montant_xaf: string; references: string[] }
export interface FinanceResult { total_debit_xaf: string; total_credit_xaf: string; net_xaf: string; findings: FinanceFinding[] }
export function financeAnalyze(transactions: unknown[], invoices: unknown[] = []): Promise<FinanceResult> {
  return api<FinanceResult>("/v1/erp/finance/analyze", { body: { transactions, invoices } });
}

export function fmt(v: string | number): string {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR") : String(v);
}
