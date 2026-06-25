// Client Import/Export Excel (binaire) — /v1/erp/import|export.
import { getToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export interface ImportEntity {
  entity: string;
  label: string;
  natural_key: string[];
  columns: { name: string; kind: string; required: boolean; enum: string[] | null }[];
}

export interface ImportPole {
  pole: string;
  label: string;
  entities: string[];
}

export interface ImportReport {
  total: number;
  valides?: number;
  importes?: number;
  mis_a_jour?: number;
  rejetes?: number;
  erreurs: { ligne: number; motifs: string[] }[];
}

// Rapport par pôle : une entrée par feuille/entité (label + compteurs).
export interface PoleReport {
  pole: string;
  rapport: Record<string, ImportReport & { label: string }>;
}

export async function listImportEntities(): Promise<{ entities: ImportEntity[]; poles: ImportPole[] }> {
  const r = await fetch(`${API_BASE}/v1/erp/import/entities`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function downloadBlob(path: string, filename: string): Promise<void> {
  const r = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadTemplate(entity: string): Promise<void> {
  return downloadBlob(`/v1/erp/import/template/${entity}`, `modele_${entity}.xlsx`);
}
export function exportEntity(entity: string): Promise<void> {
  return downloadBlob(`/v1/erp/export/${entity}`, `export_${entity}.xlsx`);
}

export async function importFile(entity: string, file: File, dryRun: boolean): Promise<ImportReport> {
  const r = await fetch(`${API_BASE}/v1/erp/import/${entity}?dry_run=${dryRun}`, {
    method: "POST",
    headers: authHeaders(),
    body: file,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ------------------------------------------------------------------ par pôle

export function downloadPoleTemplate(pole: string): Promise<void> {
  return downloadBlob(`/v1/erp/import/template/pole/${pole}`, `modele_pole_${pole}.xlsx`);
}
export function exportPole(pole: string): Promise<void> {
  return downloadBlob(`/v1/erp/export/pole/${pole}`, `export_pole_${pole}.xlsx`);
}

export async function importPoleFile(pole: string, file: File, dryRun: boolean): Promise<PoleReport> {
  const r = await fetch(`${API_BASE}/v1/erp/import/pole/${pole}?dry_run=${dryRun}`, {
    method: "POST",
    headers: authHeaders(),
    body: file,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
