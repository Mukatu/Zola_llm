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

import { synthesizeDeliverable, type Deliverable, type SynthesisResult } from "./cortex-ged";

const DELIVERABLE: Deliverable = {
  id: "id",
  mission_id: "m",
  template_id: null,
  title: "Compte rendu — entretien client",
  status: "draft",
  version: 1,
  updated_at: "2026-07-01T00:00:00Z",
  content: "x",
};

describe("cortex-ged — synthesizeDeliverable", () => {
  beforeEach(() => apiMock.mockReset());

  it("poste sur /deliverables/synthesis avec la méthode POST et le corps transmis", async () => {
    const RESULT: SynthesisResult = {
      status: "generated",
      deliverable: DELIVERABLE,
    };
    apiMock.mockResolvedValueOnce(RESULT);

    const result = await synthesizeDeliverable({
      mission_id: "m",
      notes: "Notes brutes de l'entretien client sur le périmètre du projet.",
      kind: "entretien",
      title: "Compte rendu — entretien client",
    });

    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/deliverables/synthesis", {
      method: "POST",
      body: {
        mission_id: "m",
        notes: "Notes brutes de l'entretien client sur le périmètre du projet.",
        kind: "entretien",
        title: "Compte rendu — entretien client",
      },
    });
    expect(result).toEqual(RESULT);
    expect(result.status).toBe("generated");
    expect(result.deliverable?.id).toBe("id");
  });

  it("supporte un statut unavailable sans livrable", async () => {
    const RESULT: SynthesisResult = {
      status: "unavailable",
      deliverable: null,
    };
    apiMock.mockResolvedValueOnce(RESULT);

    const result = await synthesizeDeliverable({
      mission_id: "m",
      notes: "Notes brutes suffisamment longues pour être envoyées à l'assistant.",
    });

    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/deliverables/synthesis", {
      method: "POST",
      body: {
        mission_id: "m",
        notes: "Notes brutes suffisamment longues pour être envoyées à l'assistant.",
      },
    });
    expect(result.status).toBe("unavailable");
    expect(result.deliverable).toBeNull();
  });
});
