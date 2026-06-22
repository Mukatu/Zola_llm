"use client";

import { useState } from "react";
import { Calculator, Plus, Trash2, CheckCircle2, XCircle } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { comptaValidate, fmtXaf, type JournalLineInput, type ValidationReport } from "@/lib/erp";
import { ApiError } from "@/lib/api";

const DEFAULT: JournalLineInput[] = [
  { compte: "411", libelle: "Client", debit_xaf: "1180", credit_xaf: "0" },
  { compte: "701", libelle: "Vente", debit_xaf: "0", credit_xaf: "1000" },
  { compte: "4431", libelle: "TVA collectée", debit_xaf: "0", credit_xaf: "180" },
];

export function ComptaScreen() {
  const [lignes, setLignes] = useState<JournalLineInput[]>(DEFAULT);
  const [rep, setRep] = useState<ValidationReport | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const set = (i: number, k: keyof JournalLineInput, v: string) =>
    setLignes((l) => l.map((row, j) => (j === i ? { ...row, [k]: v } : row)));
  const add = () => setLignes((l) => [...l, { compte: "", libelle: "", debit_xaf: "0", credit_xaf: "0" }]);
  const del = (i: number) => setLignes((l) => l.filter((_, j) => j !== i));

  async function validate() {
    setErr(null); setRep(null);
    try { setRep(await comptaValidate(lignes)); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible."); }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Calculator} title="Comptabilité" subtitle="Validation d'écriture SYSCOHADA (déterministe) + équilibre." />
      <Card>
        <div className="grid grid-cols-[80px_1fr_110px_110px_32px] gap-2 text-xs font-medium text-muted">
          <span>Compte</span><span>Libellé</span><span>Débit</span><span>Crédit</span><span />
        </div>
        {lignes.map((row, i) => (
          <div key={i} className="mt-1 grid grid-cols-[80px_1fr_110px_110px_32px] gap-2">
            <Inp value={row.compte} onChange={(v) => set(i, "compte", v)} />
            <Inp value={row.libelle} onChange={(v) => set(i, "libelle", v)} />
            <Inp value={row.debit_xaf} type="number" onChange={(v) => set(i, "debit_xaf", v)} />
            <Inp value={row.credit_xaf} type="number" onChange={(v) => set(i, "credit_xaf", v)} />
            <button onClick={() => del(i)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        <div className="mt-3 flex justify-between">
          <Button variant="ghost" onClick={add}><Plus className="h-4 w-4" /> Ligne</Button>
          <Button onClick={validate}>Valider l'écriture</Button>
        </div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {rep && (
        <Card className={rep.ok ? "ring-emerald-200" : "ring-red-200"}>
          <div className="mb-2 flex items-center gap-2 font-semibold">
            {rep.ok ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <XCircle className="h-5 w-5 text-red-600" />}
            {rep.ok ? "Écriture équilibrée et valide" : "Écriture invalide"}
          </div>
          <p className="text-sm text-muted">Débit {fmtXaf(rep.total_debit_xaf)} · Crédit {fmtXaf(rep.total_credit_xaf)}</p>
          {rep.errors.map((e, i) => <p key={i} className="mt-1 text-sm text-red-600">• {e}</p>)}
          {rep.warnings.map((w, i) => <p key={i} className="mt-1 text-sm text-amber-600">⚠ {w}</p>)}
        </Card>
      )}
    </div>
  );
}
