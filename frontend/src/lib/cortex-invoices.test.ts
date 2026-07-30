import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-invoices, pas le réseau.
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
  createInvoice,
  listInvoices,
  getAging,
  getInvoice,
  issueInvoice,
  payInvoice,
  cancelInvoice,
  type Invoice,
  type InvoiceDetail,
  type Aging,
} from "./cortex-invoices";

const INVOICE: Invoice = {
  id: "id",
  number: "FACT-2026-0001",
  mission_id: "m",
  client_tenant_id: "t1",
  status: "draft",
  amount: 100000,
  currency: "XAF",
  issued_date: null,
  due_date: null,
  paid_date: null,
  notes: "",
  created_at: "2026-07-29T00:00:00Z",
};

describe("cortex-invoices", () => {
  beforeEach(() => apiMock.mockReset());

  it("createInvoice appelle POST /v1/cortex/invoices", async () => {
    apiMock.mockResolvedValueOnce(INVOICE);
    const result = await createInvoice({ mission_id: "m" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices", {
      method: "POST",
      body: { mission_id: "m" },
    });
    expect(result).toEqual(INVOICE);
  });

  it("listInvoices appelle GET /v1/cortex/invoices sans query par défaut", async () => {
    apiMock.mockResolvedValueOnce([INVOICE]);
    const result = await listInvoices();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices");
    expect(result).toEqual([INVOICE]);
  });

  it("listInvoices construit la query pour status", async () => {
    apiMock.mockResolvedValueOnce([INVOICE]);
    await listInvoices({ status: "issued" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices?status=issued");
  });

  it("listInvoices construit la query pour client_tenant_id et mission_id", async () => {
    apiMock.mockResolvedValueOnce([INVOICE]);
    await listInvoices({ client_tenant_id: "t1", mission_id: "m" });
    expect(apiMock).toHaveBeenCalledWith(
      "/v1/cortex/invoices?client_tenant_id=t1&mission_id=m"
    );
  });

  it("getAging appelle GET /v1/cortex/invoices/aging", async () => {
    const aging: Aging = {
      currency: "XAF",
      total_outstanding: 50000,
      buckets: { current: 50000 },
      invoices: [],
    };
    apiMock.mockResolvedValueOnce(aging);
    const result = await getAging();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices/aging");
    expect(result).toEqual(aging);
  });

  it("getInvoice appelle GET /v1/cortex/invoices/{id}", async () => {
    const detail: InvoiceDetail = { ...INVOICE, entries: [] };
    apiMock.mockResolvedValueOnce(detail);
    const result = await getInvoice("id");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices/id");
    expect(result).toEqual(detail);
  });

  it("issueInvoice appelle POST /v1/cortex/invoices/{id}/issue avec due_days", async () => {
    apiMock.mockResolvedValueOnce({ ...INVOICE, status: "issued" });
    await issueInvoice("id", { due_days: 15 });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices/id/issue", {
      method: "POST",
      body: { due_days: 15 },
    });
  });

  it("issueInvoice envoie un body vide par défaut", async () => {
    apiMock.mockResolvedValueOnce({ ...INVOICE, status: "issued" });
    await issueInvoice("id");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices/id/issue", {
      method: "POST",
      body: {},
    });
  });

  it("payInvoice appelle POST /v1/cortex/invoices/{id}/pay", async () => {
    apiMock.mockResolvedValueOnce({ ...INVOICE, status: "paid" });
    await payInvoice("id");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices/id/pay", {
      method: "POST",
      body: {},
    });
  });

  it("cancelInvoice appelle POST /v1/cortex/invoices/{id}/cancel", async () => {
    apiMock.mockResolvedValueOnce({ ...INVOICE, status: "cancelled" });
    await cancelInvoice("id");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/invoices/id/cancel", {
      method: "POST",
      body: {},
    });
  });
});
