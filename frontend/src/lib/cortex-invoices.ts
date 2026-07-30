// Client typé — facturation d'honoraires (cockpit cabinet Zolacortex) : le
// cabinet facture son client à partir des feuilles de temps facturables
// approuvées d'une mission. Cycle draft → issued → paid (ou cancelled).
// Endpoints /v1/cortex/invoices/* (profil cortex, réservé admin).
import { api } from "./api";

export type InvoiceStatus = "draft" | "issued" | "paid" | "cancelled";

export interface Invoice {
  id: string;
  number: string;
  mission_id: string;
  client_tenant_id: string;
  status: InvoiceStatus;
  amount: number;
  currency: string;
  issued_date: string | null;
  due_date: string | null;
  paid_date: string | null;
  notes: string;
  created_at: string;
}

export interface EntryBrief {
  id: string;
  consultant_user_id: string;
  entry_date: string;
  minutes: number;
  activity: string;
  honoraires: number;
}

export interface InvoiceDetail extends Invoice {
  entries: EntryBrief[];
}

export interface AgingLine {
  id: string;
  number: string;
  client_tenant_id: string;
  amount: number;
  due_date: string | null;
  days_overdue: number;
  bucket: string;
}

export interface Aging {
  currency: string;
  total_outstanding: number;
  buckets: Record<string, number>;
  invoices: AgingLine[];
}

export interface CreateInvoiceInput {
  mission_id: string;
  notes?: string;
}

export interface ListInvoicesParams {
  client_tenant_id?: string;
  mission_id?: string;
  status?: InvoiceStatus;
}

export interface IssueInvoiceInput {
  due_days?: number;
}

export function createInvoice(input: CreateInvoiceInput): Promise<Invoice> {
  return api<Invoice>("/v1/cortex/invoices", { method: "POST", body: input });
}

export function listInvoices(params: ListInvoicesParams = {}): Promise<Invoice[]> {
  const qs = new URLSearchParams();
  if (params.client_tenant_id) qs.set("client_tenant_id", params.client_tenant_id);
  if (params.mission_id) qs.set("mission_id", params.mission_id);
  if (params.status) qs.set("status", params.status);
  const query = qs.toString();
  return api<Invoice[]>("/v1/cortex/invoices" + (query ? "?" + query : ""));
}

export function getAging(): Promise<Aging> {
  return api<Aging>("/v1/cortex/invoices/aging");
}

export function getInvoice(id: string): Promise<InvoiceDetail> {
  return api<InvoiceDetail>("/v1/cortex/invoices/" + id);
}

export function issueInvoice(id: string, input: IssueInvoiceInput = {}): Promise<Invoice> {
  return api<Invoice>("/v1/cortex/invoices/" + id + "/issue", { method: "POST", body: input });
}

export function payInvoice(id: string): Promise<Invoice> {
  return api<Invoice>("/v1/cortex/invoices/" + id + "/pay", { method: "POST", body: {} });
}

export function cancelInvoice(id: string): Promise<Invoice> {
  return api<Invoice>("/v1/cortex/invoices/" + id + "/cancel", { method: "POST", body: {} });
}
