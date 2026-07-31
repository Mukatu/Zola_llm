import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-ged, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import { memoDeliverable, type Deliverable, type MemoResult } from "./cortex-ged";

const DELIVERABLE: Deliverable = {
  id: "id",
  mission_id: "m",
  template_id: null,
  title: "Note de recherche",
  status: "draft",
  version: 1,
  updated_at: "2026-07-01T00:00:00Z",
  content: "x",
};

describe("cortex-ged — memoDeliverable", () => {
  beforeEach(() => apiMock.mockReset());

  it("poste sur /deliverables/memo avec la méthode POST et le corps transmis", async () => {
    const RESULT: MemoResult = {
      status: "generated",
      pole: "droit",
      deliverable: DELIVERABLE,
      citations: [{ index: 1, source_uri: "uri", source_id: "s1", chunk_index: 0, similarity: 0.9 }],
    };
    apiMock.mockResolvedValueOnce(RESULT);

    const result = await memoDeliverable({
      mission_id: "m",
      question: "Quel régime fiscal pour une succursale CEMAC ?",
      pole: "droit",
      title: "Note de recherche",
    });

    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/deliverables/memo", {
      method: "POST",
      body: {
        mission_id: "m",
        question: "Quel régime fiscal pour une succursale CEMAC ?",
        pole: "droit",
        title: "Note de recherche",
      },
    });
    expect(result).toEqual(RESULT);
    expect(result.status).toBe("generated");
    expect(result.deliverable?.id).toBe("id");
  });

  it("supporte un statut abstained sans livrable", async () => {
    const RESULT: MemoResult = {
      status: "abstained",
      pole: "droit",
      deliverable: null,
      citations: [],
    };
    apiMock.mockResolvedValueOnce(RESULT);

    const result = await memoDeliverable({ mission_id: "m", question: "question hors corpus" });

    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/deliverables/memo", {
      method: "POST",
      body: { mission_id: "m", question: "question hors corpus" },
    });
    expect(result.status).toBe("abstained");
    expect(result.deliverable).toBeNull();
  });
});
