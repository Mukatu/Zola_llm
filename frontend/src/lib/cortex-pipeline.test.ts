import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-pipeline, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import {
  createOpportunity,
  listOpportunities,
  getSummary,
  updateOpportunity,
  convertOpportunity,
  draftProposal,
  type Opportunity,
  type Summary,
  type ProposalDraft,
} from "./cortex-pipeline";

const OPPORTUNITY: Opportunity = {
  id: "opp1",
  title: "t",
  client_tenant_id: null,
  client_name: "Prospect Un",
  offre: "o",
  amount_estimate: 1000,
  currency: "XAF",
  stage: "lead",
  probability: 0.1,
  weighted: 100,
  expected_close_date: null,
  owner_user_id: null,
  mission_id: null,
  notes: "",
  proposal: "",
  created_at: "2026-07-29T00:00:00Z",
};

const SUMMARY: Summary = {
  by_stage: {
    lead: { count: 1, amount: 1000, weighted: 100 },
    qualified: { count: 0, amount: 0, weighted: 0 },
    proposal: { count: 0, amount: 0, weighted: 0 },
    won: { count: 0, amount: 0, weighted: 0 },
    lost: { count: 0, amount: 0, weighted: 0 },
  },
  open_count: 1,
  open_amount: 1000,
  open_weighted: 100,
  won_amount: 0,
  lost_amount: 0,
  win_rate: null,
  currency: "XAF",
};

describe("cortex-pipeline", () => {
  beforeEach(() => apiMock.mockReset());

  it("createOpportunity : POST /v1/cortex/pipeline", async () => {
    apiMock.mockResolvedValueOnce(OPPORTUNITY);
    const result = await createOpportunity({ title: "t", offre: "o" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/pipeline", { body: { title: "t", offre: "o" } });
    expect(result).toEqual(OPPORTUNITY);
  });

  it("getSummary : GET /v1/cortex/pipeline/summary", async () => {
    apiMock.mockResolvedValueOnce(SUMMARY);
    const result = await getSummary();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/pipeline/summary");
    expect(result).toEqual(SUMMARY);
  });

  it("updateOpportunity : PATCH /v1/cortex/pipeline/{id}", async () => {
    apiMock.mockResolvedValueOnce({ ...OPPORTUNITY, stage: "won" });
    const result = await updateOpportunity("id", { stage: "won" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/pipeline/id", { method: "PATCH", body: { stage: "won" } });
    expect(result).toEqual({ ...OPPORTUNITY, stage: "won" });
  });

  it("convertOpportunity : POST /v1/cortex/pipeline/{id}/convert", async () => {
    const res = { opportunity: OPPORTUNITY, mission_id: "m1" };
    apiMock.mockResolvedValueOnce(res);
    const result = await convertOpportunity("id", {});
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/pipeline/id/convert", { body: {} });
    expect(result).toEqual(res);
  });

  it("listOpportunities : construit la query (stage + mine)", async () => {
    apiMock.mockResolvedValueOnce([OPPORTUNITY]);
    const result = await listOpportunities({ stage: "lead", mine: true });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/pipeline?stage=lead&mine=true");
    expect(result).toEqual([OPPORTUNITY]);
  });

  it("listOpportunities : sans query par défaut", async () => {
    apiMock.mockResolvedValueOnce([OPPORTUNITY]);
    await listOpportunities();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/pipeline");
  });

  it("draftProposal : POST /v1/cortex/pipeline/{id}/proposal/draft", async () => {
    const DRAFT: ProposalDraft = {
      status: "generated",
      pole: "droit",
      content: "Proposition rédigée…",
      citations: [{ index: 1, source_uri: "uri", source_id: "s1", chunk_index: 0, similarity: 0.9 }],
      applied: true,
    };
    apiMock.mockResolvedValueOnce(DRAFT);
    const result = await draftProposal("id", { apply: true });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/pipeline/id/proposal/draft", {
      method: "POST",
      body: { apply: true },
    });
    expect(result).toEqual(DRAFT);
  });
});
