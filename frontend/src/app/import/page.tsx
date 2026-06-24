"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileSpreadsheet, Download, Upload, CheckCircle2, AlertTriangle } from "lucide-react";
import { Card, Button } from "@/components/ui";
import {
  listImportEntities, downloadTemplate, exportEntity, importFile,
  type ImportEntity, type ImportReport,
} from "@/lib/imports";

export default function ImportPage() {
  const [entities, setEntities] = useState<ImportEntity[]>([]);
  const [entity, setEntity] = useState("");
  const [report, setReport] = useState<ImportReport | null>(null);
  const [committed, setCommitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<File | null>(null);

  const load = useCallback(async () => {
    try {
      const { entities: e } = await listImportEntities();
      setEntities(e);
      if (e[0]) setEntity(e[0].entity);
    } catch {
      setErr("Backend indisponible.");
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const current = entities.find((e) => e.entity === entity);

  async function onFile(f: File) {
    fileRef.current = f;
    setReport(null); setCommitted(false); setErr(null); setBusy(true);
    try { setReport(await importFile(entity, f, true)); }
    catch { setErr("Fichier illisible ou backend indisponible."); }
    finally { setBusy(false); }
  }

  async function commit() {
    if (!fileRef.current) return;
    setBusy(true); setErr(null);
    try { setReport(await importFile(entity, fileRef.current, false)); setCommitted(true); }
    catch { setErr("Import impossible (backend/DB)."); }
    finally { setBusy(false); }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><FileSpreadsheet className="h-5 w-5" /></span>
        <div><h1 className="text-lg font-semibold">Import / Export de données</h1><p className="text-sm text-muted">Sans ERP : téléchargez un modèle Excel, remplissez-le, re-téléversez.</p></div>
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <Card className="flex flex-col gap-3">
        <label className="text-sm font-medium">Type de données</label>
        <select value={entity} onChange={(e) => { setEntity(e.target.value); setReport(null); setCommitted(false); }} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
          {entities.map((e) => <option key={e.entity} value={e.entity}>{e.label}</option>)}
        </select>
        {current && (
          <p className="text-xs text-muted">
            Colonnes : {current.columns.map((c) => c.name + (c.required ? "*" : "")).join(", ")}.
            {current.natural_key.length > 0 && ` Clé (mise à jour) : ${current.natural_key.join("+")}.`}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => downloadTemplate(entity)}><Download className="h-4 w-4" /> Télécharger le modèle</Button>
          <Button variant="ghost" onClick={() => exportEntity(entity)}><FileSpreadsheet className="h-4 w-4" /> Exporter l'existant</Button>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-primary px-3 py-1.5 text-sm text-white">
            <Upload className="h-4 w-4" /> Téléverser un fichier
            <input type="file" accept=".xlsx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }} />
          </label>
        </div>
      </Card>

      {busy && <Card><p className="text-sm text-muted">Traitement…</p></Card>}

      {report && (
        <Card className={(report.rejetes ?? report.erreurs.length) ? "ring-amber-200" : "ring-emerald-200"}>
          {committed ? (
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-emerald-700">
              <CheckCircle2 className="h-5 w-5" /> Import terminé : {report.importes} ajouté(s), {report.mis_a_jour} mis à jour, {report.rejetes} rejeté(s).
            </div>
          ) : (
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold">Simulation : {report.valides} ligne(s) valide(s) sur {report.total}, {report.erreurs.length} erreur(s).</span>
              <Button onClick={commit} disabled={(report.valides ?? 0) === 0}>Confirmer l'import</Button>
            </div>
          )}
          {report.erreurs.length > 0 && (
            <div className="mt-2 max-h-64 overflow-y-auto text-sm">
              {report.erreurs.map((e) => (
                <div key={e.ligne} className="flex items-start gap-2 border-b border-black/5 py-1 last:border-0">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                  <span><b>Ligne {e.ligne}</b> : {e.motifs.join(" · ")}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
