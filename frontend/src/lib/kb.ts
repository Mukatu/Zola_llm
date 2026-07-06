// Client typé — Bibliothèque documentaire (/v1/kb : catalogue, documents, lecture, recherche).
import { api } from "./api";

export interface KbFacet {
  valeur: string;
  n: number;
}
export interface KbCatalog {
  schema: string;
  documents: number;
  facettes: { module: KbFacet[]; secteur: KbFacet[]; acte: KbFacet[] };
}
export interface KbDoc {
  source_uri: string;
  source_id: string | null;
  titre: string | null;
  acte: string | null;
  nb_chunks: number;
}
export interface KbDocument {
  source_uri: string;
  source_id: string | null;
  titre: string | null;
  nb_chunks: number;
  texte: string;
  extra_metadata: Record<string, unknown>;
}
export interface KbSearchResult {
  source_uri: string;
  source_id: string | null;
  chunk_index: number;
  similarity: number;
  extrait: string;
}

export interface KbFilters {
  schema: string;
  module?: string;
  secteur?: string;
  acte?: string;
}

export function kbCatalog(schema: string): Promise<KbCatalog> {
  return api(`/v1/kb/catalog?schema=${encodeURIComponent(schema)}`);
}

export function kbDocuments(f: KbFilters): Promise<{ schema: string; total: number; documents: KbDoc[] }> {
  const qs = new URLSearchParams({ schema: f.schema });
  if (f.module) qs.set("module", f.module);
  if (f.secteur) qs.set("secteur", f.secteur);
  if (f.acte) qs.set("acte", f.acte);
  return api(`/v1/kb/documents?${qs.toString()}`);
}

export function kbDocument(schema: string, sourceUri: string): Promise<KbDocument> {
  return api(
    `/v1/kb/document?schema=${encodeURIComponent(schema)}&source_uri=${encodeURIComponent(sourceUri)}`,
  );
}

export function kbSearch(
  body: KbFilters & { q: string; k?: number },
): Promise<{ resultats: KbSearchResult[] }> {
  return api(`/v1/kb/search`, { body });
}

// ----- Documents du client (rag_tenant) : téléversement + suppression -----
export interface KbUploadResult {
  source_uri: string;
  titre: string;
  chunks: number;
  tenant_id: string;
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve((r.result as string).split(",")[1] ?? "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

export async function kbUpload(p: {
  file: File;
  module: string;
  doctype: string;
  secteur?: string;
  langue?: string;
  tenantId?: string;
  pii?: string;
}): Promise<KbUploadResult> {
  const content_b64 = await fileToBase64(p.file);
  return api(`/v1/kb/upload`, {
    body: {
      filename: p.file.name,
      content_b64,
      module: p.module,
      doctype: p.doctype,
      secteur: p.secteur,
      langue: p.langue,
      tenant_id: p.tenantId ?? "local",
      pii: p.pii ?? "none",
    },
  });
}

export function kbDelete(sourceUri: string, tenantId = "local"): Promise<{ deleted: string }> {
  return api(
    `/v1/kb/document?source_uri=${encodeURIComponent(sourceUri)}&tenant_id=${encodeURIComponent(tenantId)}`,
    { method: "DELETE" },
  );
}
