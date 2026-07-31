import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-staffing, pas le réseau.
const apiMock = vi.fn();
vi.mock("./api", () => ({
  api: (...args: unknown[]) => apiMock(...args),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
    }
  },
}));

import { upsertAssignment, listAssignments, getLoadPlan, type Assignment, type LoadPlan } from "./cortex-staffing";

const ASSIGNMENT: Assignment = {
  id: "a1",
  consultant_user_id: "c",
  mission_id: "m",
  week_start: "2026-07-27",
  allocated_minutes: 1200,
  note: "",
};

describe("upsertAssignment", () => {
  beforeEach(() => apiMock.mockReset());

  it("POST /v1/cortex/staffing avec le corps fourni", async () => {
    apiMock.mockResolvedValueOnce(ASSIGNMENT);
    const input = {
      consultant_user_id: "c",
      mission_id: "m",
      week_start: "2026-07-31",
      allocated_minutes: 1200,
    };
    const result = await upsertAssignment(input);
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/staffing", { body: input });
    expect(result).toEqual(ASSIGNMENT);
  });
});

describe("listAssignments", () => {
  beforeEach(() => apiMock.mockReset());

  it("sans paramètres n'ajoute pas de query", async () => {
    apiMock.mockResolvedValueOnce([ASSIGNMENT]);
    const result = await listAssignments();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/staffing");
    expect(result).toEqual([ASSIGNMENT]);
  });

  it("construit la query avec mission_id", async () => {
    apiMock.mockResolvedValueOnce([ASSIGNMENT]);
    await listAssignments({ mission_id: "m" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/staffing?mission_id=m");
  });

  it("construit la query avec tous les filtres", async () => {
    apiMock.mockResolvedValueOnce([ASSIGNMENT]);
    await listAssignments({ consultant_user_id: "c", mission_id: "m", from: "2026-07-27", to: "2026-08-10" });
    expect(apiMock).toHaveBeenCalledWith(
      "/v1/cortex/staffing?consultant_user_id=c&mission_id=m&from=2026-07-27&to=2026-08-10",
    );
  });
});

describe("getLoadPlan", () => {
  beforeEach(() => apiMock.mockReset());

  const PLAN: LoadPlan = {
    from_week: "2026-07-27",
    weeks: 4,
    capacity_minutes: 2400,
    consultants: [],
  };

  it("sans paramètres n'ajoute pas de query", async () => {
    apiMock.mockResolvedValueOnce(PLAN);
    const result = await getLoadPlan();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/staffing/load");
    expect(result).toEqual(PLAN);
  });

  it("GET /v1/cortex/staffing/load avec from et weeks", async () => {
    apiMock.mockResolvedValueOnce(PLAN);
    await getLoadPlan({ from: "2026-07-27", weeks: 4 });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/staffing/load?from=2026-07-27&weeks=4");
  });
});
