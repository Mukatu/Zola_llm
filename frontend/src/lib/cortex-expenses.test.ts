import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock du client HTTP : on teste la logique de cortex-expenses, pas le réseau.
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
  logExpense,
  listExpenses,
  updateExpense,
  getExpensesSummary,
  type Expense,
  type ExpenseSummary,
} from "./cortex-expenses";

const EXPENSE: Expense = {
  id: "e1",
  consultant_user_id: "u1",
  mission_id: "m",
  expense_date: "2026-07-31",
  category: "transport",
  amount: 50000,
  billable: true,
  description: "",
  status: "draft",
  invoice_id: null,
};

const SUMMARY: ExpenseSummary = {
  mission_id: "m",
  count: 1,
  total: 50000,
  billable_total: 50000,
  refacturable_approved: 0,
  by_category: { transport: 50000 },
  currency: "XAF",
};

describe("cortex-expenses", () => {
  beforeEach(() => apiMock.mockReset());

  it("logExpense poste sur /v1/cortex/expenses", async () => {
    apiMock.mockResolvedValueOnce(EXPENSE);
    const result = await logExpense({
      mission_id: "m",
      expense_date: "2026-07-31",
      category: "transport",
      amount: 50000,
    });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/expenses", {
      body: { mission_id: "m", expense_date: "2026-07-31", category: "transport", amount: 50000 },
    });
    expect(result).toEqual(EXPENSE);
  });

  it("listExpenses construit la query à partir des paramètres", async () => {
    apiMock.mockResolvedValueOnce([EXPENSE]);
    await listExpenses({ mine: true });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/expenses?mine=true");
  });

  it("listExpenses sans paramètre appelle le chemin nu", async () => {
    apiMock.mockResolvedValueOnce([EXPENSE]);
    await listExpenses();
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/expenses");
  });

  it("updateExpense patch /v1/cortex/expenses/{id}", async () => {
    apiMock.mockResolvedValueOnce({ ...EXPENSE, status: "submitted" });
    const result = await updateExpense("id", { action: "submit" });
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/expenses/id", {
      method: "PATCH",
      body: { action: "submit" },
    });
    expect(result.status).toBe("submitted");
  });

  it("getExpensesSummary appelle /v1/cortex/expenses/mission/{id}/summary", async () => {
    apiMock.mockResolvedValueOnce(SUMMARY);
    const result = await getExpensesSummary("m");
    expect(apiMock).toHaveBeenCalledWith("/v1/cortex/expenses/mission/m/summary");
    expect(result).toEqual(SUMMARY);
  });
});
