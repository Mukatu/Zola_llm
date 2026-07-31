// Client typé — plan de charge (staffing) du cockpit cabinet Zolacortex.
// Planification prospective : qui travaille sur quelle mission, quelle semaine,
// pour quelle capacité. Réservé au rôle admin (scope admin:users).
// Endpoints /v1/cortex/staffing/*.
import { api, ApiError } from "./api";
import { getCsrf } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface Assignment {
  id: string;
  consultant_user_id: string;
  mission_id: string;
  week_start: string;
  allocated_minutes: number;
  note: string;
}

export interface UpsertAssignmentInput {
  consultant_user_id: string;
  mission_id: string;
  week_start: string;
  allocated_minutes: number;
  note?: string;
}

export interface ListAssignmentsParams {
  consultant_user_id?: string;
  mission_id?: string;
  from?: string;
  to?: string;
}

export interface WeekLoad {
  week_start: string;
  allocated_minutes: number;
  capacity_minutes: number;
  available_minutes: number;
  load_pct: number | null;
  over_allocated: boolean;
}

export interface ConsultantLoad {
  consultant_user_id: string;
  total_allocated_minutes: number;
  avg_load_pct: number | null;
  over_weeks: number;
  weeks: WeekLoad[];
}

export interface LoadPlan {
  from_week: string;
  weeks: number;
  capacity_minutes: number;
  consultants: ConsultantLoad[];
}

export interface GetLoadPlanParams {
  from?: string;
  weeks?: number;
}

export function upsertAssignment(input: UpsertAssignmentInput): Promise<Assignment> {
  return api<Assignment>("/v1/cortex/staffing", { body: input });
}

export function listAssignments(params: ListAssignmentsParams = {}): Promise<Assignment[]> {
  const qs = new URLSearchParams();
  if (params.consultant_user_id) qs.set("consultant_user_id", params.consultant_user_id);
  if (params.mission_id) qs.set("mission_id", params.mission_id);
  if (params.from) qs.set("from", params.from);
  if (params.to) qs.set("to", params.to);
  const query = qs.toString();
  return api<Assignment[]>("/v1/cortex/staffing" + (query ? "?" + query : ""));
}

// Réponse 204 sans corps : fetch direct (api() suppose toujours du JSON en retour).
export async function deleteAssignment(id: string): Promise<void> {
  const res = await fetch(API_BASE + "/v1/cortex/staffing/" + id, {
    method: "DELETE",
    credentials: "include",
    headers: { "X-CSRF-Token": getCsrf() ?? "" },
  });
  if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ""));
}

export function getLoadPlan(params: GetLoadPlanParams = {}): Promise<LoadPlan> {
  const qs = new URLSearchParams();
  if (params.from) qs.set("from", params.from);
  if (params.weeks !== undefined) qs.set("weeks", String(params.weeks));
  const query = qs.toString();
  return api<LoadPlan>("/v1/cortex/staffing/load" + (query ? "?" + query : ""));
}
