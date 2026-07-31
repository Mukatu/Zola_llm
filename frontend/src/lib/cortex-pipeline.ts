// Client typé — pipeline commercial (CRM) du cabinet (Zolacortex) : opportunités
// prospects/clients, du lead à la mission. Endpoint /v1/cortex/pipeline.
import { api } from "./api";

export type Stage = "lead" | "qualified" | "proposal" | "won" | "lost";

export interface Opportunity {
  id: string;
  title: string;
  client_tenant_id: string | null;
  client_name: string | null;
  offre: string;
  amount_estimate: number;
  currency: string;
  stage: Stage;
  probability: number;
  weighted: number;
  expected_close_date: string | null;
  owner_user_id: string | null;
  mission_id: string | null;
  notes: string;
  proposal: string;
  created_at: string;
}

export interface StageSummary {
  count: number;
  amount: number;
  weighted: number;
}

export interface Summary {
  by_stage: Record<Stage, StageSummary>;
  open_count: number;
  open_amount: number;
  open_weighted: number;
  won_amount: number;
  lost_amount: number;
  win_rate: number | null;
  currency: string;
}

export interface CreateOpportunityInput {
  title: string;
  offre: string;
  amount_estimate?: number;
  client_tenant_id?: string;
  client_name?: string;
  expected_close_date?: string;
  notes?: string;
}

export interface UpdateOpportunityInput {
  title?: string;
  offre?: string;
  amount_estimate?: number;
  client_tenant_id?: string;
  client_name?: string;
  expected_close_date?: string;
  notes?: string;
  stage?: Stage;
  probability?: number;
  proposal?: string;
}

export interface ListOpportunitiesParams {
  stage?: Stage;
  mine?: boolean;
}

export interface ConvertOpportunityInput {
  ttl_hours?: number;
}

export interface ConvertOpportunityResult {
  opportunity: Opportunity;
  mission_id: string;
}

export type ProposalStatus = "generated" | "abstained" | "unavailable";

export interface ProposalCitation {
  index: number;
  source_uri: string;
  source_id: string | null;
  chunk_index: number;
  similarity: number;
}

export interface ProposalDraft {
  status: ProposalStatus;
  pole: string;
  content: string;
  citations: ProposalCitation[];
  applied: boolean;
}

export interface DraftProposalInput {
  pole?: string;
  apply?: boolean;
}

export function createOpportunity(input: CreateOpportunityInput): Promise<Opportunity> {
  return api<Opportunity>("/v1/cortex/pipeline", { body: input });
}

export function listOpportunities(params?: ListOpportunitiesParams): Promise<Opportunity[]> {
  const qs = new URLSearchParams();
  if (params?.stage) qs.set("stage", params.stage);
  if (params?.mine) qs.set("mine", "true");
  const s = qs.toString();
  return api<Opportunity[]>("/v1/cortex/pipeline" + (s ? "?" + s : ""));
}

export function getSummary(): Promise<Summary> {
  return api<Summary>("/v1/cortex/pipeline/summary");
}

export function updateOpportunity(id: string, patch: UpdateOpportunityInput): Promise<Opportunity> {
  return api<Opportunity>("/v1/cortex/pipeline/" + id, { method: "PATCH", body: patch });
}

export function convertOpportunity(id: string, input: ConvertOpportunityInput): Promise<ConvertOpportunityResult> {
  return api<ConvertOpportunityResult>("/v1/cortex/pipeline/" + id + "/convert", { body: input });
}

export function draftProposal(id: string, body: DraftProposalInput = {}): Promise<ProposalDraft> {
  return api<ProposalDraft>(`/v1/cortex/pipeline/${id}/proposal/draft`, { method: "POST", body });
}
