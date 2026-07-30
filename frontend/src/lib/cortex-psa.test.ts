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

import {
  logTime,
  listTimeEntries,
  updateTimeEntry,
  getEngagement,
  getUtilization,
  getRateCard,
  type TimeEntry,
  type Economics,
  type UtilizationRow,
  type RateCard,
} from "./cortex-psa";

const ENTRY: TimeEntry = {
  id: "e1",
  consultant_user_id: "u1",
  mission_id: "m1",
  entry_date: "2026-07-29",
  minutes: 120,
  billable: true,
  activity: "Revue de dossier",
  status: "draft",
  bill_rate: 50000,
  cost_rate: 20000,
  honoraires: 100000,
  cost: 40000,
};

describe("logTime", () => {
  beforeEach(() => apiMock.mockReset());

  it("POST /v1/cortex/psa/time-entries avec le corps fourni", async () => {
    apiMock.mockResolvedValueOnce(ENTRY);
    const input = {
      mission_id: "m1",
      entry_date: "2026-07-29",
      minutes: 120,
      billable: true,
      activity: "Revue de dossier",
    };
    const result = await logTime(input);
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/time-entries", { body: input });
    expect(result).toEqual(ENTRY);
  });
});

describe("listTimeEntries", () => {
  beforeEach(() => apiMock.mockReset());

  it("sans paramètres n'ajoute pas de query", async () => {
    apiMock.mockResolvedValueOnce([ENTRY]);
    const result = await listTimeEntries();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/time-entries");
    expect(result).toEqual([ENTRY]);
  });

  it("construit la query avec mine et mission_id", async () => {
    apiMock.mockResolvedValueOnce([ENTRY]);
    await listTimeEntries({ mine: true, mission_id: "m" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/time-entries?mission_id=m&mine=true");
  });

  it("ajoute status et limit quand fournis", async () => {
    apiMock.mockResolvedValueOnce([ENTRY]);
    await listTimeEntries({ status: "submitted", limit: 50 });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/time-entries?status=submitted&limit=50");
  });
});

describe("updateTimeEntry", () => {
  beforeEach(() => apiMock.mockReset());

  it("PATCH /v1/cortex/psa/time-entries/{id} avec action=submit", async () => {
    const submitted = { ...ENTRY, status: "submitted" as const };
    apiMock.mockResolvedValueOnce(submitted);
    const result = await updateTimeEntry("id", { action: "submit" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/time-entries/id", {
      method: "PATCH",
      body: { action: "submit" },
    });
    expect(result).toEqual(submitted);
  });
});

describe("getEngagement", () => {
  beforeEach(() => apiMock.mockReset());

  it("GET /v1/cortex/psa/engagements/{missionId}", async () => {
    const econ: Economics = {
      mission_id: "m",
      offre: "Audit",
      entries: 3,
      minutes: 600,
      hours: 10,
      billable_minutes: 480,
      billable_hours: 8,
      honoraires: 400000,
      honoraires_wip: 100000,
      cost: 160000,
      margin: 240000,
      margin_pct: 60,
      currency: "XAF",
    };
    apiMock.mockResolvedValueOnce(econ);
    const result = await getEngagement("m");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/engagements/m");
    expect(result).toEqual(econ);
  });
});

describe("getUtilization", () => {
  beforeEach(() => apiMock.mockReset());

  it("ajoute ?period= quand fourni", async () => {
    const rows: UtilizationRow[] = [
      {
        consultant_user_id: "u1",
        worked_minutes: 1000,
        billable_minutes: 800,
        available_minutes: 9600,
        occupation_pct: 8,
        activity_pct: 10,
      },
    ];
    apiMock.mockResolvedValueOnce(rows);
    const result = await getUtilization("2026-07");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/utilization?period=2026-07");
    expect(result).toEqual(rows);
  });

  it("sans période n'ajoute pas de query", async () => {
    apiMock.mockResolvedValueOnce([]);
    await getUtilization();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/utilization");
  });
});

describe("getRateCard", () => {
  beforeEach(() => apiMock.mockReset());

  it("GET /v1/cortex/psa/rate-card", async () => {
    const card: RateCard = { consultant: { bill_rate: 0, cost_rate: 0, currency: "XAF" } };
    apiMock.mockResolvedValueOnce(card);
    const result = await getRateCard();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/rate-card");
    expect(result).toEqual(card);
  });
});
