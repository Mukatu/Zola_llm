"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileSpreadsheet, Download, Upload, CheckCircle2, AlertTriangle, Layers, Wand2 } from "lucide-react";
import { Card, Button } from "@/components/ui";
import {
  listImportEntities, downloadTemplate, exportEntity, importFile,
  downloadPoleTemplate, exportPole, importPoleFile,
  type ImportEntity, type ImportPole, type ImportReport, type PoleReport, type MappingInfo,
} from "@/lib/imports";

type Mode = "entity" | "pole";

// Restitue le rapprochement automatique des colonnes (IMP-3).
function MappingNote({ mapping }: { mapping?: MappingInfo | null }) {
  if (!mapping) return null;
  const renommages = Object.entries(mapping.renommages);
  if (renommages.length === 0 && mapping.non_resolus.length === 0) return null;
  return (
    <div className="mt-2 rounded-lg bg-black/[0.03] p-2 text-xs">
      {renommages.length > 0 && (
        <div className="flex items-start gap-2 text-emerald-700">
          <Wand2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Colonnes reconnues : {renommages.map(([h, f]) => `« ${h} » → ${f}`).join(" · ")}.</span>
        </div>
      )}
      {mapping.non_resolus.length > 0 && (
        <div className="mt-1 flex items-start gap-2 text-amber-700">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Colonnes ignorées (non reconnues) : {mapping.non_resolus.join(", ")}.</span>
        </div>
      )}
    </div>
  );
}

export default function ImportPage() {
  const [mode, setMode] = useState<Mode>("pole");
  const [entities, setEntities] = useState<ImportEntity[]>([]);
  const [poles, setPoles] = useState<ImportPole[]>([]);
  const [entity, setEntity] = useState("");
  const [pole, setPole] = useState("");
  const [report, setReport] = useState<ImportReport | null>(null);
  const [poleReport, setPoleReport] = useState<PoleReport | null>(null);
  const [committed, setCommitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<File | null>(null);

  const load = useCallback(async () => {
    try {
      const { entities: e, poles: p } = await listImportEntities();
      setEntities(e);
      setPoles(p);
      if (e[0]) setEntity(e[0].entity);
      if (p[0]) setPole(p[0].pole);
    } catch {
      setErr("Backend indisponible.");
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const current = entities.find((e) => e.entity === entity);
  const currentPole = poles.find((p) => p.pole === pole);

  function reset() {
    setReport(null); setPoleReport(null); setCommitted(false); setErr(null);
    fileRef.current = null;
  }

  async function onFile(f: File) {
    fileRef.current = f;
    setReport(null); setPoleReport(null); setCommitted(false); setErr(null); setBusy(true);
    try {
      if (mode === "entity") setReport(await importFile(entity, f, true));
      else setPoleReport(await importPoleFile(pole, f, true));
    } catch { setErr("Fichier illisible ou backend indisponible."); }
    finally { setBusy(false); }
  }

  async function commit() {
    if (!fileRef.current) return;
    setBusy(true); setErr(null);
    try {
      if (mode === "entity") setReport(await importFile(entity, fileRef.current, false));
      else setPoleReport(await importPoleFile(pole, fileRef.current, false));
      setCommitted(true);
    } catch { setErr("Import impossible (backend/DB)."); }
    finally { setBusy(false); }
  }

  const tab = (m: Mode, label: string) => (
    <button
      onClick={() => { setMode(m); reset(); }}
      className={
        "rounded-lg px-3 py-1.5 text-sm font-medium transition " +
        (mode === m ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")
      }
    >
      {label}
    </button>
  );

  // somme des compteurs d'un rapport pôle (pour l'en-tête de synthèse)
  const poleTotals = poleReport
    ? Object.values(poleReport.rapport).reduce(
        (a, r) => ({
          valides: a.valides + (r.valides ?? 0),
          importes: a.importes + (r.importes ?? 0),
          mis_a_jour: a.mis_a_jour + (r.mis_a_jour ?? 0),
          rejetes: a.rejetes + (r.rejetes ?? r.erreurs.length),
        }),
        { valides: 0, importes: 0, mis_a_jour: 0, rejetes: 0 },
      )
    : null;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/15 text-forest"><FileSpreadsheet className="h-5 w-5" /></span>
        <div><h1 className="text-lg font-semibold">Import / Export de données</h1><p className="text-sm text-muted">Sans ERP : téléchargez un classeur Excel, remplissez-le, re-téléversez.</p></div>
      </div>

      <div className="flex gap-2">{tab("pole", "Par pôle (classeur)")}{tab("entity", "Par type de données")}</div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <Card className="flex flex-col gap-3">
        {mode === "pole" ? (
          <>
            <label className="text-sm font-medium">Pôle métier</label>
            <select value={pole} onChange={(e) => { setPole(e.target.value); reset(); }} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              {poles.map((p) => <option key={p.pole} value={p.pole}>{p.label}</option>)}
            </select>
            {currentPole && (
              <p className="text-xs text-muted">
                <Layers className="mr-1 inline h-3.5 w-3.5" />
                {currentPole.entities.length} feuille(s) : {currentPole.entities.join(", ")}.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" onClick={() => downloadPoleTemplate(pole)}><Download className="h-4 w-4" /> Télécharger le classeur</Button>
              <Button variant="ghost" onClick={() => exportPole(pole)}><FileSpreadsheet className="h-4 w-4" /> Exporter l'existant</Button>
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-primary px-3 py-1.5 text-sm text-white">
                <Upload className="h-4 w-4" /> Téléverser le classeur
                <input type="file" accept=".xlsx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }} />
              </label>
            </div>
          </>
        ) : (
          <>
            <label className="text-sm font-medium">Type de données</label>
            <select value={entity} onChange={(e) => { setEntity(e.target.value); reset(); }} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
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
          </>
        )}
      </Card>

      {busy && <Card><p className="text-sm text-muted">Traitement…</p></Card>}

      {mode === "entity" && report && (
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
          <MappingNote mapping={report.mapping} />
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

      {mode === "pole" && poleReport && poleTotals && (
        <Card className={poleTotals.rejetes ? "ring-amber-200" : "ring-emerald-200"}>
          {committed ? (
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-emerald-700">
              <CheckCircle2 className="h-5 w-5" /> Import terminé : {poleTotals.importes} ajouté(s), {poleTotals.mis_a_jour} mis à jour, {poleTotals.rejetes} rejeté(s).
            </div>
          ) : (
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-semibold">Simulation : {poleTotals.valides} ligne(s) valide(s), {poleTotals.rejetes} erreur(s) sur l'ensemble du classeur.</span>
              <Button onClick={commit} disabled={poleTotals.valides === 0}>Confirmer l'import</Button>
            </div>
          )}
          <div className="flex flex-col gap-2">
            {Object.entries(poleReport.rapport).map(([key, r]) => {
              const rej = r.rejetes ?? r.erreurs.length;
              return (
                <div key={key} className="rounded-lg border border-black/5 p-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{r.label}</span>
                    <span className="text-xs text-muted">
                      {committed
                        ? `${r.importes ?? 0} ajouté(s) · ${r.mis_a_jour ?? 0} maj · ${rej} rejeté(s)`
                        : `${r.valides ?? 0}/${r.total} valide(s) · ${rej} erreur(s)`}
                    </span>
                  </div>
                  <MappingNote mapping={r.mapping} />
                  {r.erreurs.length > 0 && (
                    <div className="mt-1 max-h-40 overflow-y-auto">
                      {r.erreurs.map((e) => (
                        <div key={e.ligne} className="flex items-start gap-2 py-0.5 text-xs text-amber-700">
                          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                          <span><b>Ligne {e.ligne}</b> : {e.motifs.join(" · ")}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
