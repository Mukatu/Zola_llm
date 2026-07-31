// Client typé — GED du cockpit cabinet (Zolacortex) : bibliothèque de modèles
// de livrables (admin) + livrables versionnés par mission (tout consultant).
// Endpoint /v1/cortex/ged.
import { api } from "./api";

export interface Section {
  title: string;
  guidance: string;
}

export interface Template {
  id: string;
  name: string;
  offre: string | null;
  description: string;
  sections: Section[];
  is_active: boolean;
  created_at: string;
}

export interface CreateTemplateInput {
  name: string;
  offre?: string | null;
  description?: string;
  sections: Section[];
}

export interface UpdateTemplatePatch {
  name?: string;
  description?: string;
  sections?: Section[];
  is_active?: boolean;
}

export type DeliverableStatus = "draft" | "review" | "final";

export interface DeliverableBrief {
  id: string;
  mission_id: string;
  template_id: string | null;
  title: string;
  status: DeliverableStatus;
  version: number;
  updated_at: string;
}

export interface Deliverable extends DeliverableBrief {
  content: string;
}

export interface CreateDeliverableInput {
  mission_id: string;
  template_id?: string | null;
  title: string;
}

export interface UpdateDeliverablePatch {
  title?: string;
  content?: string;
  status?: DeliverableStatus;
}

export interface ListTemplatesParams {
  offre?: string;
  active_only?: boolean;
}

export function listTemplates(params: ListTemplatesParams = {}): Promise<Template[]> {
  const qs = new URLSearchParams();
  if (params.offre) qs.set("offre", params.offre);
  if (params.active_only !== undefined) qs.set("active_only", String(params.active_only));
  const query = qs.toString();
  return api<Template[]>("/v1/cortex/ged/templates" + (query ? "?" + query : ""));
}

export function createTemplate(input: CreateTemplateInput): Promise<Template> {
  return api<Template>("/v1/cortex/ged/templates", { body: input });
}

export function updateTemplate(id: string, patch: UpdateTemplatePatch): Promise<Template> {
  return api<Template>("/v1/cortex/ged/templates/" + id, { method: "PATCH", body: patch });
}

export interface ListDeliverablesParams {
  mission_id?: string;
  status?: DeliverableStatus;
}

export function listDeliverables(params: ListDeliverablesParams = {}): Promise<DeliverableBrief[]> {
  const qs = new URLSearchParams();
  if (params.mission_id) qs.set("mission_id", params.mission_id);
  if (params.status) qs.set("status", params.status);
  const query = qs.toString();
  return api<DeliverableBrief[]>("/v1/cortex/ged/deliverables" + (query ? "?" + query : ""));
}

export function getDeliverable(id: string): Promise<Deliverable> {
  return api<Deliverable>("/v1/cortex/ged/deliverables/" + id);
}

export function createDeliverable(input: CreateDeliverableInput): Promise<Deliverable> {
  return api<Deliverable>("/v1/cortex/ged/deliverables", { body: input });
}

export function updateDeliverable(id: string, patch: UpdateDeliverablePatch): Promise<Deliverable> {
  return api<Deliverable>("/v1/cortex/ged/deliverables/" + id, { method: "PATCH", body: patch });
}

export type DraftStatus = "generated" | "abstained" | "unavailable";

export interface DraftCitation {
  index: number;
  source_uri: string;
  source_id: string | null;
  chunk_index: number;
  similarity: number;
}

export interface DraftResult {
  status: DraftStatus;
  pole: string;
  content: string;
  citations: DraftCitation[];
  applied: boolean;
}

export interface DraftDeliverableInput {
  pole?: string;
  apply?: boolean;
}

export function draftDeliverable(id: string, body: DraftDeliverableInput = {}): Promise<DraftResult> {
  return api<DraftResult>(`/v1/cortex/ged/deliverables/${id}/draft`, { method: "POST", body });
}

export type ReviewStatus = "generated" | "abstained" | "unavailable";

export interface ReviewCitation {
  index: number;
  source_uri: string;
  source_id: string | null;
  chunk_index: number;
  similarity: number;
}

export interface ReviewResult {
  status: ReviewStatus;
  pole: string;
  review: string;
  citations: ReviewCitation[];
}

export interface ReviewDeliverableInput {
  pole?: string;
}

export function reviewDeliverable(id: string, body: ReviewDeliverableInput = {}): Promise<ReviewResult> {
  return api<ReviewResult>(`/v1/cortex/ged/deliverables/${id}/review`, { method: "POST", body });
}
