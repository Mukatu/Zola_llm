import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-dashboard, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import { getDashboard, type Dashboard } from "./cortex-dashboard";

const RESPONSE: Dashboard = {
  period: "2026-07",
  currency: "XAF",
  commercial: {
    open_count: 5,
    open_amount: 12000000,
    open_weighted: 4500000,
    win_rate: 0.42,
  },
  production: {
    active_missions: 3,
    active_consultants: 4,
    worked_hours: 320,
    billable_hours: 260,
    occupation_pct: 81.25,
  },
  finance: {
    honoraires_period: 8000000,
    cost_period: 5000000,
    margin_period: 3000000,
    margin_pct: 37.5,
    wip: 1200000,
    invoiced_period: 6000000,
    collected_period: 5000000,
    outstanding: 1000000,
  },
};

describe("getDashboard", () => {
  beforeEach(() => apiMock.mockReset());

  it("appelle /v1/cortex/dashboard sans query par défaut", async () => {
    apiMock.mockResolvedValueOnce(RESPONSE);
    const result = await getDashboard();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/dashboard");
    expect(result).toEqual(RESPONSE);
  });

  it("ajoute ?period= quand fourni", async () => {
    apiMock.mockResolvedValueOnce(RESPONSE);
    await getDashboard("2026-07");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/dashboard?period=2026-07");
  });
});
