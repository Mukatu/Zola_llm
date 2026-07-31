// Client typé — notes de frais du cockpit cabinet (Zolacortex) : saisie des
// dépenses de mission par les consultants, synthèse cabinet pour refacturation.
// Endpoints /v1/cortex/expenses/*.
import { api } from "./api";

export type ExpenseStatus = "draft" | "submitted" | "approved" | "rejected";

export type ExpenseCategory =
  | "transport"
  | "hebergement"
  | "repas"
  | "fournitures"
  | "honoraires_tiers"
  | "autre";

export interface Expense {
  id: string;
  consultant_user_id: string;
  mission_id: string;
  expense_date: string;
  category: string;
  amount: number;
  billable: boolean;
  description: string;
  status: ExpenseStatus;
  invoice_id: string | null;
}

export interface LogExpenseInput {
  mission_id: string;
  expense_date: string;
  category: string;
  amount: number;
  billable?: boolean;
  description?: string;
}

export interface ListExpensesParams {
  mission_id?: string;
  mine?: boolean;
  status?: ExpenseStatus;
}

export interface UpdateExpensePatch {
  category?: string;
  amount?: number;
  billable?: boolean;
  description?: string;
  action?: "submit" | "approve" | "reject";
}

export interface ExpenseSummary {
  mission_id: string;
  count: number;
  total: number;
  billable_total: number;
  refacturable_approved: number;
  by_category: Record<string, number>;
  currency: string;
}

export function logExpense(input: LogExpenseInput): Promise<Expense> {
  return api<Expense>("/v1/cortex/expenses", { body: input });
}

export function listExpenses(params: ListExpensesParams = {}): Promise<Expense[]> {
  const qs = new URLSearchParams();
  if (params.mission_id) qs.set("mission_id", params.mission_id);
  if (params.mine !== undefined) qs.set("mine", String(params.mine));
  if (params.status) qs.set("status", params.status);
  const query = qs.toString();
  return api<Expense[]>("/v1/cortex/expenses" + (query ? "?" + query : ""));
}

export function updateExpense(id: string, patch: UpdateExpensePatch): Promise<Expense> {
  return api<Expense>("/v1/cortex/expenses/" + id, { method: "PATCH", body: patch });
}

export function getExpensesSummary(missionId: string): Promise<ExpenseSummary> {
  return api<ExpenseSummary>("/v1/cortex/expenses/mission/" + missionId + "/summary");
}
