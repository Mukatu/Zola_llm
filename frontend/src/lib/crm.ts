// Client typé — CRM persisté (registre vivant) sur /v1/crm/*.
// Réutilise les types d'analyse de data.ts (pipeline/score/relance partagés).
import { api } from "./api";
import type { PipelineStats, LeadScore, RelanceItem } from "./data";

export interface CustomerRec {
  id: string;
  id_externe: string;
  nom: string;
  type: string;
  email: string | null;
  telephone: string | null;
  secteur: string | null;
  source: string;
  date_creation: string | null;
  derniere_interaction: string | null;
  country: string;
}

export interface OpportunityRec {
  id: string;
  id_externe: string;
  client: string;
  libelle: string;
  montant_xaf: string;
  etape: string;
  probabilite: string | null;
  date_creation: string | null;
  date_cloture_prevue: string | null;
  derniere_interaction: string | null;
  country: string;
}

export interface QuoteLine {
  libelle: string;
  montant_ht_xaf: string;
}
export interface QuoteRec {
  id: string;
  id_externe: string;
  numero: string;
  client: string;
  date_emission: string | null;
  date_validite: string | null;
  statut: string;
  lignes: QuoteLine[];
  montant_ht_xaf: string;
  montant_ttc_xaf: string;
  invoice_id: string | null;
  country: string;
}

export interface InteractionRec {
  id: string;
  customer_id: string | null;
  opportunity_id: string | null;
  type: string;
  date: string | null;
  resume: string;
  created_at: string | null;
}

export interface CrmAnalyze {
  pipeline: PipelineStats;
  scores: Record<string, LeadScore>;
  relances: RelanceItem[];
}

export interface ForecastMonth {
  mois: string;
  brut_xaf: string;
  pondere_xaf: string;
}
export interface Forecast {
  prevision: ForecastMonth[];
  sans_date_pondere_xaf: string;
  total_pondere_xaf: string;
}

// ----- Clients -----
export function listCustomers(): Promise<{ customers: CustomerRec[] }> {
  return api("/v1/crm/customers");
}
export function createCustomer(b: {
  id_externe: string;
  nom: string;
  type?: string;
  source?: string;
  secteur?: string;
}): Promise<CustomerRec> {
  return api("/v1/crm/customers", { body: b });
}

// ----- Opportunités -----
export function listOpportunities(): Promise<{ opportunities: OpportunityRec[] }> {
  return api("/v1/crm/opportunities");
}
export function createOpportunity(b: {
  id_externe: string;
  client: string;
  libelle: string;
  montant_xaf: string;
  etape?: string;
  date_cloture_prevue?: string | null;
}): Promise<OpportunityRec> {
  return api("/v1/crm/opportunities", { body: b });
}
export function moveStage(id: string, etape: string): Promise<OpportunityRec> {
  return api(`/v1/crm/opportunities/${id}/stage`, { method: "PATCH", body: { etape } });
}
export function deleteOpportunity(id: string): Promise<{ deleted: string }> {
  return api(`/v1/crm/opportunities/${id}`, { method: "DELETE" });
}

// ----- Devis -----
export function listQuotes(): Promise<{ quotes: QuoteRec[] }> {
  return api("/v1/crm/quotes");
}
export function createQuote(b: {
  id_externe: string;
  numero: string;
  client: string;
  date_emission: string;
  statut?: string;
  lignes?: QuoteLine[];
  montant_ht_xaf: string;
  montant_ttc_xaf: string;
}): Promise<QuoteRec> {
  return api("/v1/crm/quotes", { body: b });
}
export function convertQuote(id: string): Promise<{ quote: QuoteRec; invoice: { numero: string } }> {
  return api(`/v1/crm/quotes/${id}/convert`, { method: "POST", body: {} });
}

// ----- Interactions (journal) -----
export function listInteractions(params?: {
  customer_id?: string;
  opportunity_id?: string;
}): Promise<{ interactions: InteractionRec[] }> {
  const q = new URLSearchParams();
  if (params?.customer_id) q.set("customer_id", params.customer_id);
  if (params?.opportunity_id) q.set("opportunity_id", params.opportunity_id);
  const qs = q.toString();
  return api(`/v1/crm/interactions${qs ? `?${qs}` : ""}`);
}
export function createInteraction(b: {
  opportunity_id?: string;
  customer_id?: string;
  type: string;
  date: string;
  resume: string;
}): Promise<InteractionRec> {
  return api("/v1/crm/interactions", { body: b });
}

// ----- Analyse / prévision (sur le registre) -----
export function crmAnalyzeStore(): Promise<CrmAnalyze> {
  return api("/v1/crm/analyze");
}
export function crmForecast(): Promise<Forecast> {
  return api("/v1/crm/forecast");
}
