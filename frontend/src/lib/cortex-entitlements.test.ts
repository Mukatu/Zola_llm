import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-entitlements, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import { getActiveGrant } from "./cortex-entitlements";

describe("getActiveGrant", () => {
  beforeEach(() => apiMock.mockReset());

  it("retourne null quand aucune licence active (404 attendu)", async () => {
    apiMock.mockRejectedValueOnce({ status: 404, detail: "no_active_license" });
    await expect(getActiveGrant("t1")).resolves.toBeNull();
  });

  it("propage les erreurs non-404 (ne les avale pas)", async () => {
    apiMock.mockRejectedValueOnce({ status: 403, detail: "forbidden" });
    await expect(getActiveGrant("t1")).rejects.toMatchObject({ status: 403 });
  });

  it("retourne le grant + jeton quand présent", async () => {
    const grant = { id: "g1", tenant_id: "t1", tier: "business", token: "a.b.c" };
    apiMock.mockResolvedValueOnce(grant);
    await expect(getActiveGrant("t1")).resolves.toEqual(grant);
  });
});
