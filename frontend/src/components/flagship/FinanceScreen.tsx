"use client";

import { useState } from "react";
import { Wallet, Plus, Trash2, ShieldAlert } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { financeAnalyze, fmt, type FinanceResult } from "@/lib/data";
import { ApiError } from "@/lib/api";

interface Tx { id_externe: string; date_operation: string; libelle: string; montant_xaf: string; sens: string }

const DEFAULT: Tx[] = [
  { id_externe: "T1", date_operation: "2026-06-10", libelle: "Loyer", montant_xaf: "200000", sens: "debit" },
  { id_externe: "T2", date_operation: "2026-06-10", libelle: "Loyer", montant_xaf: "200000", sens: "debit" },
  { id_externe: "T3", date_operation: "2026-06-12", libelle: "Achat matériel", montant_xaf: "1500000", sens: "debit" },
  { id_externe: "T4", date_operation: "2026-06-15", libelle: "Encaissement client", montant_xaf: "3000000", sens: "credit" },
];

export function FinanceScreen() {
  const [txs, setTxs] = useState<Tx[]>(DEFAULT);
  const [res, setRes] = useState<FinanceResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const set = (i: number, k: keyof Tx, v: string) => setTxs((l) => l.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const add = () => setTxs((l) => [...l, { id_externe: `T${l.length + 1}`, date_operation: "2026-06-20", libelle: "", montant_xaf: "0", sens: "debit" }]);

  async function run() {
    setErr(null); setRes(null);
    try { setRes(await financeAnalyze(txs)); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible."); }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Wallet} title="Finance / Trésorerie" subtitle="Détection d'anomalies (doublons/dépassements/échéances) déterministe." />
      <Card>
        <div className="grid grid-cols-[120px_1fr_120px_90px_32px] gap-2 text-xs font-medium text-muted">
          <span>Date</span><span>Libellé</span><span>Montant</span><span>Sens</span><span />
        </div>
        {txs.map((row, i) => (
          <div key={i} className="mt-1 grid grid-cols-[120px_1fr_120px_90px_32px] gap-2">
            <Inp value={row.date_operation} type="date" onChange={(v) => set(i, "date_operation", v)} />
            <Inp value={row.libelle} onChange={(v) => set(i, "libelle", v)} />
            <Inp value={row.montant_xaf} type="number" onChange={(v) => set(i, "montant_xaf", v)} />
            <select value={row.sens} onChange={(e) => set(i, "sens", e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 text-sm">
              <option value="debit">débit</option><option value="credit">crédit</option>
            </select>
            <button onClick={() => setTxs((l) => l.filter((_, j) => j !== i))} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        <div className="mt-3 flex justify-between">
          <Button variant="ghost" onClick={add}><Plus className="h-4 w-4" /> Mouvement</Button>
          <Button onClick={run}>Analyser</Button>
        </div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {res && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Card><div className="text-xs text-muted">Débits</div><div className="mt-1 font-semibold">{fmt(res.total_debit_xaf)} XAF</div></Card>
            <Card><div className="text-xs text-muted">Crédits</div><div className="mt-1 font-semibold">{fmt(res.total_credit_xaf)} XAF</div></Card>
            <Card><div className="text-xs text-muted">Flux net</div><div className={"mt-1 font-semibold " + (Number(res.net_xaf) < 0 ? "text-red-600" : "text-emerald-600")}>{fmt(res.net_xaf)} XAF</div></Card>
          </div>
          <Card>
            <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold"><ShieldAlert className="h-4 w-4" /> Anomalies ({res.findings.length})</h2>
            {res.findings.length === 0 && <p className="text-sm text-muted">Aucune anomalie détectée.</p>}
            {res.findings.map((f, i) => (
              <div key={i} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
                <span className="flex items-center gap-2"><Urg level={f.severity} /> {f.libelle}</span>
                <span className="text-muted">{fmt(f.montant_xaf)} XAF</span>
              </div>
            ))}
          </Card>
        </>
      )}
    </div>
  );
}
