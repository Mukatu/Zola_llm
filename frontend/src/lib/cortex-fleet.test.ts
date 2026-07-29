import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-fleet, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import { getFleet, type FleetResponse } from "./cortex-fleet";

const RESPONSE: FleetResponse = {
  summary: {
    clients: 1,
    boxes_connected: 1,
    licenses_active: 1,
    licenses_expiring_soon: 0,
    licenses_expired_or_revoked: 0,
    licenses_none: 0,
  },
  rows: [
    {
      tenant_id: "t1",
      name: "Client Un",
      country: "cg",
      is_active: true,
      box_provisioned: true,
      box_connected: true,
      license_status: "active",
      license_tier: "business",
      license_expires_at: "2026-12-01T00:00:00Z",
      license_days_left: 90,
      active_missions: 2,
    },
  ],
};

describe("getFleet", () => {
  beforeEach(() => apiMock.mockReset());

  it("appelle /v1/cortex/fleet sans query par défaut", async () => {
    apiMock.mockResolvedValueOnce(RESPONSE);
    const result = await getFleet();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/fleet");
    expect(result).toEqual(RESPONSE);
  });

  it("ajoute ?expiring_days= quand fourni", async () => {
    apiMock.mockResolvedValueOnce(RESPONSE);
    await getFleet(15);
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/fleet?expiring_days=15");
  });
});
