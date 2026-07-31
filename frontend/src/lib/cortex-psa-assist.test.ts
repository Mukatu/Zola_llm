import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-psa, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import { assistTimeEntries, type AssistTimeResult, type TimeSuggestion } from "./cortex-psa";

const SUGGESTION: TimeSuggestion = {
  entry_date: "2026-07-27",
  minutes: 180,
  hours: 3,
  activity: "Audit ACME",
  billable: true,
  mission_id: "m1",
  mission_label: "Audit ACME",
};

describe("assistTimeEntries", () => {
  beforeEach(() => apiMock.mockReset());

  it("POST /v1/cortex/psa/time-entries/assist avec le corps fourni", async () => {
    const result: AssistTimeResult = { status: "suggested", suggestions: [SUGGESTION] };
    apiMock.mockResolvedValueOnce(result);
    const input = { narrative: "Lundi 3h sur l'audit ACME", week_start: "2026-07-27" };
    const out = await assistTimeEntries(input);
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/time-entries/assist", {
      method: "POST",
      body: input,
    });
    expect(out).toEqual(result);
    expect(out.status).toBe("suggested");
    expect(out.suggestions[0]).toEqual(SUGGESTION);
  });

  it("accepte une réponse sans suggestion (liste vide)", async () => {
    const result: AssistTimeResult = { status: "suggested", suggestions: [] };
    apiMock.mockResolvedValueOnce(result);
    const out = await assistTimeEntries({ narrative: "rien de particulier" });
    expect(out.suggestions).toEqual([]);
  });

  it("propage le statut unavailable quand le LLM est indisponible", async () => {
    const result: AssistTimeResult = { status: "unavailable", suggestions: [] };
    apiMock.mockResolvedValueOnce(result);
    const out = await assistTimeEntries({ narrative: "Lundi 3h sur l'audit ACME" });
    expect(out.status).toBe("unavailable");
  });
});
