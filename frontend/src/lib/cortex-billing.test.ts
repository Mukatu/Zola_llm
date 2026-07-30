import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-billing, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import { getBilling, getPricing, type BillingResponse, type PricingResponse } from "./cortex-billing";

const RESPONSE: BillingResponse = {
  period: "2026-07",
  currency: "XAF",
  rows: [
    {
      tenant_id: "t1",
      name: "Client Un",
      tier: "business",
      requests: 1200,
      tokens: 340000,
      cost: {
        monthly_base: 150000,
        included_requests: 1000,
        overage_requests: 200,
        overage_per_1k: 5000,
        overage_cost: 1000,
        total: 151000,
        currency: "XAF",
      },
    },
  ],
  total_requests: 1200,
  total_tokens: 340000,
  total_cost: 151000,
};

const PRICING: PricingResponse = {
  business: { monthly_base: 150000, included_requests: 1000, overage_per_1k: 5000, currency: "XAF" },
};

describe("getBilling", () => {
  beforeEach(() => apiMock.mockReset());

  it("appelle /v1/cortex/billing sans query par défaut", async () => {
    apiMock.mockResolvedValueOnce(RESPONSE);
    const result = await getBilling();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/billing");
    expect(result).toEqual(RESPONSE);
  });

  it("ajoute ?period= quand fourni", async () => {
    apiMock.mockResolvedValueOnce(RESPONSE);
    await getBilling("2026-07");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/billing?period=2026-07");
  });
});

describe("getPricing", () => {
  beforeEach(() => apiMock.mockReset());

  it("appelle /v1/cortex/billing/pricing", async () => {
    apiMock.mockResolvedValueOnce(PRICING);
    const result = await getPricing();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/billing/pricing");
    expect(result).toEqual(PRICING);
  });
});
