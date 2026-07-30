// Client typé — usage & facturation du cockpit cabinet Zolacortex : consommation et
// coût par tenant sur une période donnée, plus le barème de tarification par palier.
// Endpoints /v1/cortex/billing et /v1/cortex/billing/pricing.
import { api } from "./api";

export interface CostBreakdown {
  monthly_base: number;
  included_requests: number;
  overage_requests: number;
  overage_per_1k: number;
  overage_cost: number;
  total: number;
  currency: string;
}

export interface BillingRow {
  tenant_id: string;
  name: string | null;
  tier: string | null;
  requests: number;
  tokens: number;
  cost: CostBreakdown;
}

export interface BillingResponse {
  period: string;
  currency: string;
  rows: BillingRow[];
  total_requests: number;
  total_tokens: number;
  total_cost: number;
}

export interface PricingTier {
  monthly_base: number;
  included_requests: number;
  overage_per_1k: number;
  currency: string;
}

export type PricingResponse = Record<string, PricingTier>;

export function getBilling(period?: string): Promise<BillingResponse> {
  const qs = period ? "?period=" + period : "";
  return api<BillingResponse>("/v1/cortex/billing" + qs);
}

export function getPricing(): Promise<PricingResponse> {
  return api<PricingResponse>("/v1/cortex/billing/pricing");
}
