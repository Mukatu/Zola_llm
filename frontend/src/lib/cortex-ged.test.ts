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

import {
  listTemplates,
  createTemplate,
  createDeliverable,
  updateDeliverable,
  getDeliverable,
  type Template,
  type Deliverable,
} from "./cortex-ged";

const TEMPLATE: Template = {
  id: "tpl-1",
  name: "T",
  offre: "audit",
  description: "",
  sections: [],
  is_active: true,
  created_at: "2026-07-01T00:00:00Z",
};

const DELIVERABLE: Deliverable = {
  id: "id",
  mission_id: "m",
  template_id: null,
  title: "D",
  status: "draft",
  version: 1,
  updated_at: "2026-07-01T00:00:00Z",
  content: "x",
};

describe("cortex-ged", () => {
  beforeEach(() => apiMock.mockReset());

  it("listTemplates ajoute la query offre", async () => {
    apiMock.mockResolvedValueOnce([TEMPLATE]);
    const result = await listTemplates({ offre: "audit" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/templates?offre=audit");
    expect(result).toEqual([TEMPLATE]);
  });

  it("createTemplate poste sur /templates", async () => {
    apiMock.mockResolvedValueOnce(TEMPLATE);
    await createTemplate({ name: "T", sections: [] });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/templates", {
      body: { name: "T", sections: [] },
    });
  });

  it("createDeliverable poste sur /deliverables", async () => {
    apiMock.mockResolvedValueOnce(DELIVERABLE);
    await createDeliverable({ mission_id: "m", title: "D" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/deliverables", {
      body: { mission_id: "m", title: "D" },
    });
  });

  it("updateDeliverable patch sur /deliverables/{id}", async () => {
    apiMock.mockResolvedValueOnce(DELIVERABLE);
    await updateDeliverable("id", { content: "x" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/deliverables/id", {
      method: "PATCH",
      body: { content: "x" },
    });
  });

  it("getDeliverable récupère /deliverables/{id}", async () => {
    apiMock.mockResolvedValueOnce(DELIVERABLE);
    const result = await getDeliverable("id");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/ged/deliverables/id");
    expect(result).toEqual(DELIVERABLE);
  });
});
