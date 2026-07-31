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

import { getMarginAlerts, getAlertsBrief, type AlertsResult, type AlertsBriefResult, type MarginAlert } from "./cortex-psa";

const ALERT: MarginAlert = {
  type: "marge_negative",
  severity: "high",
  mission_id: "m1",
  offre: "Audit ACME",
  message: "Marge négative sur la mission Audit ACME.",
  impact: -150000,
  metrics: { margin: -150000, margin_pct: -12 },
};

describe("getMarginAlerts", () => {
  beforeEach(() => apiMock.mockReset());

  it("GET /v1/cortex/psa/alerts", async () => {
    const result: AlertsResult = {
      count: 1,
      thresholds: { margin_low_pct: 15, wip_alert_xaf: 2000000, min_honoraires_xaf: 100000 },
      alerts: [ALERT],
    };
    apiMock.mockResolvedValueOnce(result);
    const out = await getMarginAlerts();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/alerts");
    expect(out).toEqual(result);
    expect(out.alerts[0]).toEqual(ALERT);
  });

  it("accepte un résultat sans alerte (count=0)", async () => {
    const result: AlertsResult = {
      count: 0,
      thresholds: { margin_low_pct: 15, wip_alert_xaf: 2000000, min_honoraires_xaf: 100000 },
      alerts: [],
    };
    apiMock.mockResolvedValueOnce(result);
    const out = await getMarginAlerts();
    expect(out.count).toBe(0);
    expect(out.alerts).toEqual([]);
  });
});

describe("getAlertsBrief", () => {
  beforeEach(() => apiMock.mockReset());

  it("POST /v1/cortex/psa/alerts/brief avec un corps vide", async () => {
    const result: AlertsBriefResult = { status: "generated", brief: "Synthèse des alertes marge.", count: 1 };
    apiMock.mockResolvedValueOnce(result);
    const out = await getAlertsBrief();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/psa/alerts/brief", { method: "POST", body: {} });
    expect(out).toEqual(result);
  });

  it("propage le statut unavailable quand l'assistant est indisponible", async () => {
    const result: AlertsBriefResult = { status: "unavailable", brief: "", count: 0 };
    apiMock.mockResolvedValueOnce(result);
    const out = await getAlertsBrief();
    expect(out.status).toBe("unavailable");
  });

  it("propage le statut empty quand il n'y a aucune alerte", async () => {
    const result: AlertsBriefResult = { status: "empty", brief: "", count: 0 };
    apiMock.mockResolvedValueOnce(result);
    const out = await getAlertsBrief();
    expect(out.status).toBe("empty");
  });
});
