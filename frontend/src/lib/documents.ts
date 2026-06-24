// Client typé — Documents (artefacts générés) + génération RH.
import { api } from "./api";

export interface DocumentRec {
  id: string; type: string; metier: string; titre: string; contenu: string;
  tags: string[]; statut: string; created_at: string | null;
}

export function listDocuments(type?: string): Promise<{ documents: DocumentRec[] }> {
  const q = type ? `?type=${encodeURIComponent(type)}` : "";
  return api(`/v1/erp/documents${q}`);
}
export function createDocument(b: { type: string; titre: string; contenu: string; metier?: string; source_ref?: string }): Promise<DocumentRec> {
  return api("/v1/erp/documents", { body: b });
}
export function deleteDocument(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/documents/${id}`, { method: "DELETE" });
}
export function hrGeneratePrompt(b: { type: string; code_emploi?: string; code_vacance?: string }): Promise<{ type: string; titre: string; prompt: string }> {
  return api("/v1/erp/hr/generate", { body: b });
}
export function hrGenerateContracts(b: { matricules: string[]; type_contrat?: string; date_debut?: string }): Promise<{ contrats: { matricule: string; contenu: string }[] }> {
  return api("/v1/erp/hr/contracts/generate", { body: b });
}
