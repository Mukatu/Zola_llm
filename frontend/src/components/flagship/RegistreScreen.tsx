"use client";

import { useCallback, useEffect, useState } from "react";
import { Receipt, Plus, Trash2, Check, Activity } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { fmtXaf } from "@/lib/erp";
import { fmt } from "@/lib/data";
import { ApiError } from "@/lib/api";
import { getFxRates, type FxRate } from "@/lib/fx";
import {
  listInvoices, createInvoice, payInvoice, deleteInvoice, reconcile,
  type InvoiceRec, type TxInput, type ReconcileResult,
} from "@/lib/store";

// Traduit les codes d'erreur backend en messages FR sobres.
function invoiceError(e: unknown): string {
  if (!(e instanceof ApiError)) return "Création impossible (backend/DB).";
  let detail = e.detail;
  try {
    const p = JSON.parse(e.detail) as { detail?: string };
    if (p?.detail) detail = p.detail;
  } catch { /* detail brut */ }
  if (detail.startsWith("taux_non_valide")) {
    return `Taux ${detail.split(":")[1] ?? ""} non validé — saisissez-le dans « Devises / Change ».`;
  }
  if (detail.includes("montant_devise_requis")) return "Indiquez le montant dans la devise choisie.";
  return "Création impossible (backend/DB).";
}

const DEFAULT_TX: TxInput[] = [
  { id_externe: "T1", date_operation: "2026-06-12", libelle: "Virement client", montant_xaf: "1180", sens: "credit" },
];

export function RegistreScreen() {
  const [invoices, setInvoices] = useState<InvoiceRec[]>([]);
  const [txs, setTxs] = useState<TxInput[]>(DEFAULT_TX);
  const [res, setRes] = useState<ReconcileResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rates, setRates] = useState<FxRate[]>([]);
  const [form, setForm] = useState({ numero: "", tiers: "", date_emission: "2026-06-10", montant_ttc_xaf: "", devise: "XAF" });

  const selRate = rates.find((r) => r.devise === form.devise);
  const enDevise = form.devise !== "XAF";
  const apercuXaf =
    enDevise && form.montant_ttc_xaf && selRate?.taux_vers_xaf
      ? Number(form.montant_ttc_xaf) * Number(selRate.taux_vers_xaf)
      : null;

  const runReconcile = useCallback(async (list: TxInput[]) => {
    try { setRes(await reconcile(list)); setErr(null); }
    catch (e) { setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible."); }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const { invoices: inv } = await listInvoices();
      setInvoices(inv);
      await runReconcile(txs);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, [txs, runReconcile]);

  useEffect(() => {
    refresh(); // au montage
    getFxRates().then((v) => setRates(v.rates)).catch(() => setRates([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Clôture vivante : recalcul auto à chaque changement de mouvements (débounce).
  useEffect(() => {
    const t = setTimeout(() => runReconcile(txs), 350);
    return () => clearTimeout(t);
  }, [txs, runReconcile]);

  async function add() {
    if (!form.numero || !form.montant_ttc_xaf) return;
    const base = { numero: form.numero, tiers: form.tiers, date_emission: form.date_emission };
    const payload = enDevise
      ? { ...base, devise: form.devise, montant_ttc_devise: form.montant_ttc_xaf, montant_ht_devise: form.montant_ttc_xaf }
      : { ...base, montant_ttc_xaf: form.montant_ttc_xaf, montant_ht_xaf: form.montant_ttc_xaf };
    try {
      await createInvoice(payload);
      setForm({ numero: "", tiers: "", date_emission: form.date_emission, montant_ttc_xaf: "", devise: form.devise });
      setErr(null);
      await refresh();
    } catch (e) { setErr(invoiceError(e)); }
  }
  async function pay(id: string) { try { await payInvoice(id); await refresh(); } catch { setErr("Action impossible."); } }
  async function del(id: string) { try { await deleteInvoice(id); await refresh(); } catch { setErr("Suppression impossible."); } }

  const setTx = (i: number, k: keyof TxInput, v: string) =>
    setTxs((l) => l.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const addTx = () => setTxs((l) => [...l, { id_externe: `T${l.length + 1}`, date_operation: "2026-06-15", libelle: "Encaissement", montant_xaf: "0", sens: "credit" }]);

  const c = res?.cloture;
  const taux = c ? Number(c.taux_lettrage_pct) : 0;

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={Receipt} title="Registre & clôture vivante" subtitle="Factures persistées + réconciliation temps réel (la clôture devient un non-événement)." />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {/* Bandeau clôture vivante */}
      <Card>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Activity className="h-4 w-4 text-emerald-600" /> Clôture vivante</div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Taux de lettrage" value={(c ? c.taux_lettrage_pct : "0") + " %"} />
          <Kpi label="Lettrées / en attente" value={c ? `${c.lettrees} / ${c.en_attente}` : "—"} />
          <Kpi label="Encours clients" value={fmtXaf(c?.encours_clients_xaf ?? "0")} />
          <Kpi label="Lettré" value={fmtXaf(c?.montant_lettre_xaf ?? "0")} />
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-black/10">
          <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${taux}%` }} />
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Registre des factures */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Registre des factures de vente</h2>
          <div className="mb-1 grid grid-cols-[1fr_1fr_100px_74px_36px] gap-2">
            <Inp value={form.numero} onChange={(v) => setForm({ ...form, numero: v })} placeholder="N°" />
            <Inp value={form.tiers} onChange={(v) => setForm({ ...form, tiers: v })} placeholder="Client" />
            <Inp value={form.montant_ttc_xaf} type="number" onChange={(v) => setForm({ ...form, montant_ttc_xaf: v })} placeholder={enDevise ? `TTC ${form.devise}` : "TTC"} />
            <select
              value={form.devise}
              onChange={(e) => setForm({ ...form, devise: e.target.value })}
              className="rounded-lg border border-black/10 bg-white px-1 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            >
              {(rates.length ? rates : [{ devise: "XAF" } as FxRate]).map((r) => (
                <option key={r.devise} value={r.devise}>{r.devise}</option>
              ))}
            </select>
            <button onClick={add} className="grid place-items-center rounded-lg bg-forest text-white"><Plus className="h-4 w-4" /></button>
          </div>
          <div className="mb-3 min-h-[1rem] text-xs">
            {enDevise && apercuXaf !== null && (
              <span className="text-muted">≈ {fmtXaf(String(Math.round(apercuXaf)))} au taux {fmt(selRate?.taux_vers_xaf ?? "0")}</span>
            )}
            {enDevise && selRate && !selRate.validated && (
              <span className="text-amber-700">Taux {form.devise} non validé — à saisir/valider dans « Devises / Change ».</span>
            )}
          </div>
          {invoices.length === 0 && <p className="text-sm text-muted">Aucune facture. Ajoutez-en une.</p>}
          {invoices.map((inv) => (
            <div key={inv.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{inv.numero}</b> · {inv.tiers || "—"}</span>
              <span className="flex items-center gap-2">
                <span className="text-muted">
                  {inv.montant_ttc_devise && inv.devise !== "XAF" && (
                    <span className="mr-1 text-[11px]">{fmt(inv.montant_ttc_devise)} {inv.devise} →</span>
                  )}
                  {fmtXaf(inv.montant_ttc_xaf)}
                </span>
                {inv.payee
                  ? <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">payée</span>
                  : <button onClick={() => pay(inv.id)} title="Marquer payée" className="text-emerald-600 hover:text-emerald-800"><Check className="h-4 w-4" /></button>}
                <button onClick={() => del(inv.id)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
              </span>
            </div>
          ))}
        </Card>

        {/* Mouvements (encaissements) */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Encaissements (rapprochés en continu)</h2>
          {txs.map((t, i) => (
            <div key={i} className="mb-1 grid grid-cols-[110px_1fr_110px] gap-2">
              <Inp value={t.date_operation} type="date" onChange={(v) => setTx(i, "date_operation", v)} />
              <Inp value={t.libelle} onChange={(v) => setTx(i, "libelle", v)} />
              <Inp value={t.montant_xaf} type="number" onChange={(v) => setTx(i, "montant_xaf", v)} />
            </div>
          ))}
          <Button variant="ghost" onClick={addTx}><Plus className="h-4 w-4" /> Mouvement</Button>

          {res && res.rapprochements.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-semibold text-muted">Rapprochements</div>
              {res.rapprochements.map((r, i) => (
                <div key={i} className="text-sm text-emerald-700">✓ {r.invoice_id.slice(0, 8)}… ↔ {r.transaction_id} ({fmtXaf(r.montant_xaf)})</div>
              ))}
            </div>
          )}
          {res && res.factures_en_attente.length > 0 && (
            <div className="mt-2">
              <div className="text-xs font-semibold text-muted">En attente</div>
              {res.factures_en_attente.map((f) => (
                <div key={f.invoice_id} className="text-sm text-amber-700">• {f.numero} · {f.tiers} ({fmtXaf(f.montant_ttc_xaf)})</div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-black/[0.03] p-2">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 font-semibold">{value}</div>
    </div>
  );
}
