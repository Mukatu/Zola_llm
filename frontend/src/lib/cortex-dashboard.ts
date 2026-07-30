// Client typé — tableau de bord de pilotage (Zolacortex) : vue d'ensemble
// commerciale, production et finance du cabinet sur une période donnée.
// Endpoint /v1/cortex/dashboard.
import { api } from "./api";

export interface DashboardCommercial {
  open_count: number;
  open_amount: number;
  open_weighted: number;
  win_rate: number | null;
}

export interface DashboardProduction {
  active_missions: number;
  active_consultants: number;
  worked_hours: number;
  billable_hours: number;
  occupation_pct: number | null;
}

export interface DashboardFinance {
  honoraires_period: number;
  cost_period: number;
  margin_period: number;
  margin_pct: number | null;
  wip: number;
  invoiced_period: number;
  collected_period: number;
  outstanding: number;
}

export interface Dashboard {
  period: string;
  currency: string;
  commercial: DashboardCommercial;
  production: DashboardProduction;
  finance: DashboardFinance;
}

export function getDashboard(period?: string): Promise<Dashboard> {
  const qs = period ? "?period=" + period : "";
  return api<Dashboard>("/v1/cortex/dashboard" + qs);
}
