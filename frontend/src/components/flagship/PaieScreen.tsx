"use client";

import { useState } from "react";
import { Wallet, AlertCircle } from "lucide-react";
import { Card, Button } from "../ui";
import { ApiError } from "@/lib/api";
import { payrollCompute, fmtXaf, type PayrollResult } from "@/lib/erp";

/** Écran phare Paie : formulaire → moteur déterministe /v1/erp/payroll/compute. */
export function PaieScreen() {
  const [brut, setBrut] = useState("450000");
  const [sim, setSim] = useState(true);
  const [res, setRes] = useState<PayrollResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function compute() {
    setLoading(true); setErr(null); setRes(null);
    try {
      setRes(await payrollCompute(brut, sim));
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setErr("Barème non validé : activez la simulation pour un calcul indicatif.");
      } else {
        setErr(e instanceof ApiError ? e.message : "Service indisponible (hors-ligne ?).");
      }
    } finally { setLoading(false); }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Wallet className="h-5 w-5" /></span>
        <div>
          <h1 className="text-lg font-semibold">Paie</h1>
          <p className="text-sm text-muted">Bulletin déterministe (CNSS/CIPRES/IRPP). Calcul exact côté moteur.</p>
        </div>
      </div>

      <Card>
        <label className="block text-sm font-medium">Salaire brut mensuel (XAF)</label>
        <input
          type="number" value={brut} onChange={(e) => setBrut(e.target.value)}
          className="mt-1 w-full rounded-xl border border-black/10 bg-white p-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
        />
        <label className="mt-3 flex items-center gap-2 text-sm text-muted">
          <input type="checkbox" checked={sim} onChange={(e) => setSim(e.target.checked)} />
          Mode simulation (barème non encore validé)
        </label>
        <div className="mt-3 flex justify-end">
          <Button onClick={compute} disabled={loading}>{loading ? "Calcul…" : "Calculer"}</Button>
        </div>
      </Card>

      {err && (
        <Card className="ring-amber-200">
          <div className="flex items-start gap-2 text-amber-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><p className="text-sm">{err}</p></div>
        </Card>
      )}

      {res && (
        <Card>
          {!res["barème_validé"] && (
            <div className="mb-3 rounded-lg bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800">
              Simulation — barème non validé (à confirmer par un expert paie).
            </div>
          )}
          <Row label="Brut" value={res.brut_xaf} strong />
          {Object.entries(res.cotisations_salariales).map(([k, v]) => <Row key={k} label={`Cotisation ${k}`} value={`- ${fmtXaf(v)}`} />)}
          <Row label="Base imposable" value={res.base_imposable_xaf} />
          <Row label="IRPP" value={`- ${fmtXaf(res.irpp_xaf)}`} />
          <div className="my-2 border-t border-black/10" />
          <Row label="Net à payer" value={res.net_a_payer_xaf} strong />
          <div className="my-2 border-t border-black/10" />
          <Row label="Coût employeur" value={res.cout_employeur_xaf} muted />
        </Card>
      )}
    </div>
  );
}

function Row({ label, value, strong, muted }: { label: string; value: string; strong?: boolean; muted?: boolean }) {
  return (
    <div className={"flex items-center justify-between py-1 text-sm " + (muted ? "text-muted" : "")}>
      <span className={strong ? "font-semibold" : ""}>{label}</span>
      <span className={strong ? "font-semibold" : ""}>{value.startsWith("-") ? value : fmtXaf(value)}</span>
    </div>
  );
}
