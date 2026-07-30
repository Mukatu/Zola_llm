// Client typé — PSA cockpit cabinet (Zolacortex) : feuilles de temps, économie
// de mission, taux d'occupation, barème d'honoraires. Endpoints /v1/cortex/psa/*.
import { api } from "./api";

export type TimeEntryStatus = "draft" | "submitted" | "approved" | "rejected";

export interface TimeEntry {
  id: string;
  consultant_user_id: string;
  mission_id: string;
  entry_date: string;
  minutes: number;
  billable: boolean;
  activity: string;
  status: TimeEntryStatus;
  bill_rate: number;
  cost_rate: number;
  honoraires: number;
  cost: number;
}

export interface LogTimeInput {
  mission_id: string;
  entry_date: string;
  minutes: number;
  billable: boolean;
  activity: string;
}

export interface ListTimeEntriesParams {
  mission_id?: string;
  mine?: boolean;
  status?: TimeEntryStatus;
  limit?: number;
}

export interface UpdateTimeEntryPatch {
  minutes?: number;
  billable?: boolean;
  activity?: string;
  action?: "submit" | "approve" | "reject";
}

export interface Economics {
  mission_id: string;
  offre: string;
  entries: number;
  minutes: number;
  hours: number;
  billable_minutes: number;
  billable_hours: number;
  honoraires: number;
  honoraires_wip: number;
  cost: number;
  margin: number;
  margin_pct: number | null;
  currency: string;
}

export interface UtilizationRow {
  consultant_user_id: string;
  worked_minutes: number;
  billable_minutes: number;
  available_minutes: number;
  occupation_pct: number | null;
  activity_pct: number | null;
}

export type RateCard = Record<string, { bill_rate: number; cost_rate: number; currency: string }>;

export function logTime(input: LogTimeInput): Promise<TimeEntry> {
  return api<TimeEntry>("/v1/cortex/psa/time-entries", { body: input });
}

export function listTimeEntries(params: ListTimeEntriesParams = {}): Promise<TimeEntry[]> {
  const qs = new URLSearchParams();
  if (params.mission_id) qs.set("mission_id", params.mission_id);
  if (params.mine !== undefined) qs.set("mine", String(params.mine));
  if (params.status) qs.set("status", params.status);
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  const query = qs.toString();
  return api<TimeEntry[]>("/v1/cortex/psa/time-entries" + (query ? "?" + query : ""));
}

export function updateTimeEntry(id: string, patch: UpdateTimeEntryPatch): Promise<TimeEntry> {
  return api<TimeEntry>("/v1/cortex/psa/time-entries/" + id, { method: "PATCH", body: patch });
}

export function getEngagement(missionId: string): Promise<Economics> {
  return api<Economics>("/v1/cortex/psa/engagements/" + missionId);
}

export function getUtilization(period?: string): Promise<UtilizationRow[]> {
  return api<UtilizationRow[]>("/v1/cortex/psa/utilization" + (period ? "?period=" + period : ""));
}

export function getRateCard(): Promise<RateCard> {
  return api<RateCard>("/v1/cortex/psa/rate-card");
}
