// Client typé — surface cabinet (Zolacortex) : gestion des comptes utilisateurs.
// Réservé au rôle admin (scope admin:users). Endpoints /v1/cortex/accounts/*.
import { api } from "./api";

export interface Account {
  id: string;
  email: string;
  display_name: string;
  role: string;
  tenant_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface CreateAccountInput {
  email: string;
  display_name: string;
  role: string;
  tenant_id?: string;
  password?: string;
}

export interface CreateAccountResult {
  account: Account;
  temp_password: string | null;
}

export interface UpdateAccountInput {
  display_name?: string;
  role?: string;
  tenant_id?: string;
  is_active?: boolean;
}

export interface ResetResult {
  password: string;
}

export function listAccounts(): Promise<Account[]> {
  return api<Account[]>("/v1/cortex/accounts");
}

export function createAccount(input: CreateAccountInput): Promise<CreateAccountResult> {
  return api<CreateAccountResult>("/v1/cortex/accounts", { body: input });
}

export function updateAccount(id: string, patch: UpdateAccountInput): Promise<Account> {
  return api<Account>("/v1/cortex/accounts/" + id, { method: "PATCH", body: patch });
}

export function resetPassword(id: string): Promise<ResetResult> {
  return api<ResetResult>("/v1/cortex/accounts/" + id + "/reset-password", { method: "POST", body: {} });
}
