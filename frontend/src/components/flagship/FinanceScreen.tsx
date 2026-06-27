"use client";

import { useCallback, useEffect, useState } from "react";
import { Wallet, Plus, Trash2, Landmark, ArrowDownToLine, ArrowUpFromLine, Clock, CheckCircle2, ScrollText, TrendingUp, Download } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { fmt } from "@/lib/data";
import { ApiError } from "@/lib/api";
import {
  listBankAccounts,
  createBankAccount,
  deleteBankAccount,
  listCashFlows,
  createCashFlow,
  deleteCashFlow,
  treasuryPosition,
  approveCashFlow,
  treasuryReconcile,
  treasuryPilotage,
  downloadTreasuryPilotage,
  type BankAccountRec,
  type CashFlowRec,
  type PositionTresorerie,
  type ReleveLigne,
  type ReconcileResult,
  type Previsionnel,
  type IndicateursTreso,
} from "@/lib/treasury";

const TODAY = new Date().toISOString().slice(0, 10);
const TYPE_LABEL: Record<string, string> = { banque: "Banque", caisse: "Caisse", mobile_money: "Mobile money" };

const DEMO_ACCOUNTS = [
  { code: "BGFI", libelle: "BGFI Bank — compte courant", banque: "BGFI", type: "banque", solde_initial_xaf: "5000000" },
  { code: "CAISSE", libelle: "Caisse centrale", banque: "—", type: "caisse", solde_initial_xaf: "300000" },
  { code: "MOMO", libelle: "Mobile Money MTN", banque: "MTN", type: "mobile_money", solde_initial_xaf: "150000" },
];
const DEMO_FLOWS = [
  { reference: "ENC-001", compte_code: "BGFI", sens: "encaissement", montant_xaf: "3000000", date_operation: TODAY, statut: "realise", libelle: "Règlement client ACME" },
  { reference: "DEC-001", compte_code: "BGFI", sens: "decaissement", montant_xaf: "1200000", date_operation: TODAY, statut: "realise", libelle: "Fournisseur HBM" },
  { reference: "DEC-002", compte_code: "BGFI", sens: "decaissement", montant_xaf: "2500000", date_operation: TODAY, statut: "prevu", libelle: "Salaires (à venir)" },
  { reference: "ENC-002", compte_code: "CAISSE", sens: "encaissement", montant_xaf: "200000", date_operation: TODAY, statut: "prevu", libelle: "Ventes comptant" },
];

export function FinanceScreen() {
  const [accounts, setAccounts] = useState<BankAccountRec[]>([]);
  const [flows, setFlows] = useState<CashFlowRec[]>([]);
  const [position, setPosition] = useState<PositionTresorerie | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [accForm, setAccForm] = useState({ code: "", libelle: "", type: "banque", solde: "" });
  const [flowForm, setFlowForm] = useState({ compte: "", sens: "encaissement", statut: "realise", montant: "", libelle: "" });
  const [releve, setReleve] = useState<ReleveLigne[]>([{ date: TODAY, montant_xaf: "", sens: "encaissement" }]);
  const [recRes, setRecRes] = useState<ReconcileResult | null>(null);
  const [prev, setPrev] = useState<Previsionnel | null>(null);
  const [indic, setIndic] = useState<IndicateursTreso | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [a, f, p, pil] = await Promise.all([
        listBankAccounts(),
        listCashFlows(),
        treasuryPosition(),
        treasuryPilotage(90),
      ]);
      setAccounts(a.accounts);
      setFlows(f.flows);
      setPosition(p.position);
      setPrev(pil.previsionnel);
      setIndic(pil.indicateurs);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function addAccount() {
    if (!accForm.code || !accForm.libelle) return;
    try {
      await createBankAccount({
        code: accForm.code,
        libelle: accForm.libelle,
        type: accForm.type,
        solde_initial_xaf: accForm.solde || "0",
      });
      setAccForm({ code: "", libelle: "", type: "banque", solde: "" });
      await refresh();
    } catch {
      setErr("Création du compte impossible (backend/DB).");
    }
  }
  async function addFlow() {
    if (!flowForm.compte || !flowForm.montant) return;
    try {
      await createCashFlow({
        reference: `${flowForm.sens === "encaissement" ? "ENC" : "DEC"}-${Date.now()}`,
        compte_code: flowForm.compte,
        sens: flowForm.sens,
        statut: flowForm.statut,
        montant_xaf: flowForm.montant,
        date_operation: TODAY,
        libelle: flowForm.libelle,
      });
      setFlowForm({ ...flowForm, montant: "", libelle: "" });
      await refresh();
    } catch {
      setErr("Création du flux impossible (backend/DB).");
    }
  }
  async function seedDemo() {
    try {
      for (const a of DEMO_ACCOUNTS) await createBankAccount(a);
      for (const f of DEMO_FLOWS) await createCashFlow(f);
      await refresh();
    } catch {
      setErr("Initialisation de la démo impossible (backend/DB).");
    }
  }
  async function approve(id: string) {
    try {
      const r = await approveCashFlow(id);
      if (!r.execute && r.requiert_n2) setErr("Décaissement validé N1 — une 2ᵉ validation (N2) est requise.");
      else setErr(null);
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 409 ? "Décaissement déjà exécuté." : "Approbation impossible.");
    }
  }
  async function runReconcile() {
    const lignes = releve.filter((l) => l.montant_xaf !== "");
    if (lignes.length === 0) return;
    try {
      setRecRes(await treasuryReconcile(lignes));
      await refresh();
    } catch {
      setErr("Rapprochement impossible (backend/DB).");
    }
  }
  const setReleveLine = (i: number, k: keyof ReleveLigne, v: string) =>
    setReleve((l) => l.map((r, j) => (j === i ? { ...r, [k]: v } : r)));

  const isEmpty = accounts.length === 0;
  const aVenir = position ? position.total_projete_xaf - position.total_realise_xaf : 0;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <FlagshipHeader
        icon={Wallet}
        title="Finance / Trésorerie"
        subtitle="Comptes, flux (réalisés & prévus) et position de trésorerie consolidée — registre vivant."
      />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {position && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Comptes" value={String(position.nb_comptes)} />
          <Kpi label="Position réalisée" value={fmt(position.total_realise_xaf) + " XAF"} />
          <Kpi label="Position projetée" value={fmt(position.total_projete_xaf) + " XAF"} />
          <Kpi label="Flux à venir (net)" value={(aVenir >= 0 ? "+" : "") + fmt(aVenir) + " XAF"} />
        </div>
      )}

      {isEmpty && (
        <Card>
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-muted">
              Aucun compte. La position est <b>persistante</b> : chargez une démo ou créez un compte.
            </p>
            <Button onClick={seedDemo}><Plus className="h-4 w-4" /> Charger une démo</Button>
          </div>
        </Card>
      )}

      {/* Position par compte */}
      {position && position.par_compte.length > 0 && (
        <Card>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Landmark className="h-4 w-4 text-indigo-600" /> Position par compte
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th className="py-1 pr-2">Compte</th>
                  <th className="pr-2 text-right">Encaissé</th>
                  <th className="pr-2 text-right">Décaissé</th>
                  <th className="pr-2 text-right">Solde réalisé</th>
                  <th className="pr-2 text-right">Solde projeté</th>
                </tr>
              </thead>
              <tbody>
                {position.par_compte.map((c) => (
                  <tr key={c.code} className="border-t border-black/5">
                    <td className="py-1 pr-2">
                      <b>{c.code}</b> <span className="text-xs text-muted">{TYPE_LABEL[c.type] ?? c.type}</span>
                    </td>
                    <td className="pr-2 text-right text-emerald-700">{fmt(c.encaisse_xaf)}</td>
                    <td className="pr-2 text-right text-red-600">{fmt(c.decaisse_xaf)}</td>
                    <td className="pr-2 text-right font-semibold">{fmt(c.solde_realise_xaf)}</td>
                    <td className={"pr-2 text-right " + (c.solde_projete_xaf < 0 ? "font-semibold text-red-600" : "text-muted")}>{fmt(c.solde_projete_xaf)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Pilotage : prévisionnel + indicateurs */}
      {prev && indic && (
        <Card>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <TrendingUp className="h-4 w-4 text-indigo-600" /> Pilotage (prévisionnel 90 j)
            </h2>
            <Button variant="ghost" onClick={() => downloadTreasuryPilotage(90)}>
              <Download className="h-4 w-4" /> Exporter
            </Button>
          </div>
          <div className="mb-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <Mini label="Position fin de période" value={fmt(prev.position_finale_xaf) + " XAF"} />
            <Mini label="DSO / DPO" value={`${indic.dso_jours} / ${indic.dpo_jours} j`} />
            <Mini label="BFR" value={fmt(indic.bfr_xaf) + " XAF"} />
            <Mini label="Runway" value={indic.runway_mois != null ? indic.runway_mois + " mois" : "—"} />
          </div>
          {prev.decouvert_periode && (
            <p className="mb-2 text-sm text-red-600">
              ⚠ Découvert prévu en {prev.decouvert_periode} (solde {fmt(prev.decouvert_xaf ?? 0)} XAF).
            </p>
          )}
          {/* Courbe de solde projeté (barres) */}
          <div className="flex items-end gap-1 pt-2" style={{ height: 90 }}>
            {prev.periodes.map((p) => {
              const max = Math.max(1, ...prev.periodes.map((x) => Math.abs(x.solde_projete_xaf)));
              const h = (Math.abs(p.solde_projete_xaf) / max) * 80;
              const neg = p.solde_projete_xaf < 0;
              return (
                <div key={p.libelle} className="flex flex-1 flex-col items-center justify-end" title={`${p.libelle} : ${fmt(p.solde_projete_xaf)} XAF`}>
                  <div className={"w-full rounded-t " + (neg ? "bg-red-400" : "bg-indigo-400")} style={{ height: `${Math.max(2, h)}%` }} />
                  <span className="text-[9px] text-muted">{p.libelle}</span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Comptes */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Comptes de trésorerie</h2>
          <div className="mb-2 grid grid-cols-[80px_1fr_90px_36px] gap-2">
            <Inp value={accForm.code} onChange={(v) => setAccForm({ ...accForm, code: v })} placeholder="Code" />
            <Inp value={accForm.libelle} onChange={(v) => setAccForm({ ...accForm, libelle: v })} placeholder="Libellé" />
            <select value={accForm.type} onChange={(e) => setAccForm({ ...accForm, type: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              {["banque", "caisse", "mobile_money"].map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
            </select>
            <button onClick={addAccount} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          <Inp value={accForm.solde} type="number" onChange={(v) => setAccForm({ ...accForm, solde: v })} placeholder="Solde initial XAF" className="mb-2 w-full" />
          {accounts.map((a) => (
            <div key={a.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{a.code}</b> · {a.libelle}</span>
              <span className="flex items-center gap-2 text-muted">
                {fmt(a.solde_initial_xaf)} XAF
                <button onClick={() => deleteBankAccount(a.id).then(refresh)} className="hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
              </span>
            </div>
          ))}
        </Card>

        {/* Flux */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Flux de trésorerie</h2>
          <div className="mb-2 grid grid-cols-[80px_110px_100px_90px_36px] gap-2">
            <Inp value={flowForm.compte} onChange={(v) => setFlowForm({ ...flowForm, compte: v })} placeholder="Compte" />
            <select value={flowForm.sens} onChange={(e) => setFlowForm({ ...flowForm, sens: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              <option value="encaissement">encaissement</option>
              <option value="decaissement">décaissement</option>
            </select>
            <select value={flowForm.statut} onChange={(e) => setFlowForm({ ...flowForm, statut: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              <option value="realise">réalisé</option>
              <option value="prevu">prévu</option>
            </select>
            <Inp value={flowForm.montant} type="number" onChange={(v) => setFlowForm({ ...flowForm, montant: v })} placeholder="Montant" />
            <button onClick={addFlow} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          <Inp value={flowForm.libelle} onChange={(v) => setFlowForm({ ...flowForm, libelle: v })} placeholder="Libellé" className="mb-2 w-full" />
          {flows.length === 0 && <p className="text-sm text-muted">Aucun flux.</p>}
          {flows.map((f) => {
            const Icon = f.sens === "encaissement" ? ArrowDownToLine : ArrowUpFromLine;
            return (
              <div key={f.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
                <span className="flex items-center gap-2">
                  <Icon className={"h-4 w-4 " + (f.sens === "encaissement" ? "text-emerald-600" : "text-red-600")} />
                  <span>{f.compte_code} · {f.libelle || f.reference}</span>
                  {f.statut === "prevu" && <Clock className="h-3.5 w-3.5 text-amber-500" />}
                </span>
                <span className="flex items-center gap-2 text-muted">
                  {fmt(f.montant_xaf)}
                  {f.sens === "decaissement" && f.statut === "prevu" && f.niveau_validation === "" && (
                    <button onClick={() => approve(f.id)} title="Approuver" className="text-emerald-600 hover:text-emerald-800"><CheckCircle2 className="h-4 w-4" /></button>
                  )}
                  {f.sens === "decaissement" && f.statut === "prevu" && f.niveau_validation === "n1" && (
                    <button onClick={() => approve(f.id)} title="Valider N2" className="flex items-center gap-1 text-amber-600 hover:text-amber-800">
                      <span className="text-[10px] font-semibold">N1✓</span><CheckCircle2 className="h-4 w-4" />
                    </button>
                  )}
                  {f.rapproche && <span className="rounded-full bg-emerald-100 px-1.5 text-[10px] text-emerald-700">rappr.</span>}
                  <button onClick={() => deleteCashFlow(f.id).then(refresh)} className="hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
                </span>
              </div>
            );
          })}
        </Card>
      </div>

      {/* Rapprochement bancaire */}
      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <ScrollText className="h-4 w-4 text-indigo-600" /> Rapprochement bancaire
          </h2>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setReleve((l) => [...l, { date: TODAY, montant_xaf: "", sens: "encaissement" }])}>
              <Plus className="h-4 w-4" /> Ligne
            </Button>
            <Button onClick={runReconcile}>Rapprocher</Button>
          </div>
        </div>
        <p className="mb-2 text-xs text-muted">Saisissez les lignes du relevé : elles sont appariées aux flux réalisés (montant + sens + date à ±5 j).</p>
        {releve.map((l, i) => (
          <div key={i} className="mb-1 grid grid-cols-[130px_1fr_130px] gap-2">
            <Inp value={l.date} type="date" onChange={(v) => setReleveLine(i, "date", v)} />
            <Inp value={l.montant_xaf} type="number" onChange={(v) => setReleveLine(i, "montant_xaf", v)} placeholder="Montant" />
            <select value={l.sens} onChange={(e) => setReleveLine(i, "sens", e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              <option value="encaissement">encaissement</option>
              <option value="decaissement">décaissement</option>
            </select>
          </div>
        ))}
        {recRes && (
          <div className="mt-2 text-sm">
            <div className="font-semibold">
              {recRes.rapprochements.length} rapproché(s) · taux {recRes.taux_rapprochement_pct}%
            </div>
            {recRes.releve_non_rapproche.length > 0 && (
              <div className="text-amber-700">Lignes de relevé sans correspondance : {recRes.releve_non_rapproche.map((i) => i + 1).join(", ")}</div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </Card>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-black/[0.03] p-2">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 font-semibold">{value}</div>
    </div>
  );
}
