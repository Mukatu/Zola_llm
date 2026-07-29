import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-audit, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import { listAudit, listAuditActions, type AuditEvent } from "./cortex-audit";

const EVENTS: AuditEvent[] = [
  {
    id: 1,
    occurred_at: "2026-07-29T10:00:00Z",
    category: "gouvernance",
    event: "license.issued",
    actor_type: "admin",
    actor_id: "u1",
    tenant_id: "t1",
    severity: "info",
    payload: { summary: "Licence émise pour Client Un", actor_email: "admin@polaris.cg" },
  },
];

const ACTIONS = ["license.issued", "account.created", "box_credential.revoked", "mission_created"];

describe("listAudit", () => {
  beforeEach(() => apiMock.mockReset());

  it("appelle /v1/cortex/audit sans query par défaut", async () => {
    apiMock.mockResolvedValueOnce(EVENTS);
    const result = await listAudit();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/audit");
    expect(result).toEqual(EVENTS);
  });

  it("ajoute event et limit en query string quand fournis", async () => {
    apiMock.mockResolvedValueOnce(EVENTS);
    const result = await listAudit({ event: "license.issued", limit: 50 });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/audit?event=license.issued&limit=50");
    expect(result).toEqual(EVENTS);
  });

  it("ajoute category et tenantId en query string quand fournis", async () => {
    apiMock.mockResolvedValueOnce(EVENTS);
    await listAudit({ category: "all", tenantId: "t1" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/audit?category=all&tenant_id=t1");
  });
});

describe("listAuditActions", () => {
  beforeEach(() => apiMock.mockReset());

  it("appelle /v1/cortex/audit/actions", async () => {
    apiMock.mockResolvedValueOnce(ACTIONS);
    const result = await listAuditActions();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/audit/actions");
    expect(result).toEqual(ACTIONS);
  });
});
