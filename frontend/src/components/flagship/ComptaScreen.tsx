"use client";

import { useCallback, useEffect, useState } from "react";
import { Calculator, Plus, Trash2, CheckCircle2, XCircle, Save, Activity, Sparkles } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { comptaValidate, comptaSuggest, fmtXaf, type JournalLineInput, type ValidationReport } from "@/lib/erp";
import { ApiError } from "@/lib/api";
import {
  createEntry, listEntries, getBalance, deleteEntry,
  type Balance, type EntryRec,
} from "@/lib/store";

const DEFAULT: JournalLineInput[] = [
  { compte: "411", libelle: "Client", debit_xaf: "1180", credit_xaf: "0" },
  { compte: "701", libelle: "Vente", debit_xaf: "0", credit_xaf: "1000" },
  { compte: "4431", libelle: "TVA collectée", debit_xaf: "0", credit_xaf: "180" },
];

export function ComptaScreen() {
  const [lignes, setLignes] = useState<JournalLineInput[]>(DEFAULT);
  const [libelle, setLibelle] = useState("Vente");
  const [rep, setRep] = useState<ValidationReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [entries, setEntries] = useState<EntryRec[]>([]);

  const set = (i: number, k: keyof JournalLineInput, v: string) =>
    setLignes((l) => l.map((row, j) => (j === i ? { ...row, [k]: v } : row)));
  const add = () => setLignes((l) => [...l, { compte: "", libelle: "", debit_xaf: "0", credit_xaf: "0" }]);
  const del = (i: number) => setLignes((l) => l.filter((_, j) => j !== i));

  const refresh = useCallback(async () => {
    try {
      const [b, e] = await Promise.all([getBalance(), listEntries()]);
      setBalance(b);
      setEntries(e.entries);
    } catch {
      /* backend/DB indisponible : on laisse la saisie/validation locale fonctionner */
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function autoCategorize() {
    setErr(null);
    try {
      const updated = await Promise.all(
        lignes.map(async (row) => {
          if (row.compte.trim() || !row.libelle.trim()) return row;
          const sens = Number(row.debit_xaf) > 0 ? "debit" : Number(row.credit_xaf) > 0 ? "credit" : undefined;
          const { suggestions } = await comptaSuggest(row.libelle, sens);
          return suggestions[0] ? { ...row, compte: suggestions[0].compte } : row;
        }),
      );
      setLignes(updated);
    } catch (e) {
      setErr(e instanceof ApiError ? "Suggestion indisponible." : "Service indisponible.");
    }
  }

  async function validate() {
    setErr(null);
    setRep(null);
    try {
      setRep(await comptaValidate(lignes));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Service indisponible.");
    }
  }

  async function save() {
    setErr(null);
    try {
      await createEntry({
        date_ecriture: new Date().toISOString().slice(0, 10),
        journal: "OD",
        libelle,
        lignes: lignes.map((l) => ({
          compte: l.compte,
          libelle: l.libelle,
          debit_xaf: l.debit_xaf,
          credit_xaf: l.credit_xaf,
        })),
      });
      setRep(null);
      await refresh();
    } catch (e) {
      setErr(
        e instanceof ApiError && e.status === 422
          ? "Écriture rejetée : déséquilibrée ou compte inconnu au plan SYSCOHADA."
          : "Enregistrement impossible (backend/DB requis).",
      );
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Calculator} title="Comptabilité" subtitle="Saisie validée SYSCOHADA + balance vivante (clôture continue)." />

      <Card>
        <div className="mb-2 flex items-center gap-2">
          <span className="text-xs font-medium text-muted">Libellé</span>
          <Inp value={libelle} onChange={setLibelle} className="flex-1" />
        </div>
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
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex gap-2">
            <Button variant="ghost" onClick={add}><Plus className="h-4 w-4" /> Ligne</Button>
            <Button variant="ghost" onClick={autoCategorize}><Sparkles className="h-4 w-4" /> Suggérer comptes</Button>
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={validate}>Valider</Button>
            <Button onClick={save}><Save className="h-4 w-4" /> Enregistrer</Button>
          </div>
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

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Balance vivante */}
        <Card>
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm font-semibold"><Activity className="h-4 w-4 text-emerald-600" /> Balance vivante</span>
            {balance && (
              <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (balance.equilibre ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700")}>
                {balance.equilibre ? "équilibrée" : "déséquilibrée"}
              </span>
            )}
          </div>
          {!balance || balance.comptes.length === 0
            ? <p className="text-sm text-muted">Aucune écriture enregistrée.</p>
            : (
              <>
                <div className="grid grid-cols-[1fr_90px_90px] gap-2 text-xs font-medium text-muted">
                  <span>Compte</span><span className="text-right">Débit</span><span className="text-right">Crédit</span>
                </div>
                {balance.comptes.map((c) => (
                  <div key={c.compte} className="grid grid-cols-[1fr_90px_90px] gap-2 border-b border-black/5 py-1 text-sm last:border-0">
                    <span className="font-mono">{c.compte}</span>
                    <span className="text-right">{fmtXaf(c.debit_xaf)}</span>
                    <span className="text-right">{fmtXaf(c.credit_xaf)}</span>
                  </div>
                ))}
                <div className="mt-1 grid grid-cols-[1fr_90px_90px] gap-2 pt-1 text-sm font-semibold">
                  <span>Total</span>
                  <span className="text-right">{fmtXaf(balance.total_debit_xaf)}</span>
                  <span className="text-right">{fmtXaf(balance.total_credit_xaf)}</span>
                </div>
              </>
            )}
        </Card>

        {/* Écritures récentes */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Écritures enregistrées ({entries.length})</h2>
          {entries.length === 0 && <p className="text-sm text-muted">Aucune.</p>}
          {entries.map((e) => (
            <div key={e.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span>{e.date_ecriture} · <b>{e.journal}</b> · {e.libelle}</span>
              <span className="flex items-center gap-2">
                <span className="text-muted">{fmtXaf(e.total_debit_xaf)}</span>
                <button onClick={async () => { await deleteEntry(e.id); refresh(); }} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
              </span>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
