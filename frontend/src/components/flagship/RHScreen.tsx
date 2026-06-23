"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Users, LayoutGrid, BarChart3, CalendarClock, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { fmtXaf } from "@/lib/erp";
import { ApiError } from "@/lib/api";
import {
  listEmployees, createEmployee, deleteEmployee, getDashboard, getEcheancier,
  type EmployeeRec, type HrDashboard, type HrEcheance,
} from "@/lib/hr";

type Tab = "registre" | "dashboard" | "echeancier";

const EMPTY = { matricule: "", nom_complet: "", genre: "H", date_embauche: "2026-01-01", poste: "", departement: "", salaire_base_xaf: "" };

export function RHScreen() {
  const [tab, setTab] = useState<Tab>("registre");
  const [emps, setEmps] = useState<EmployeeRec[]>([]);
  const [dash, setDash] = useState<HrDashboard | null>(null);
  const [ech, setEch] = useState<HrEcheance[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setErr(null);
    try {
      const [e, d, k] = await Promise.all([listEmployees(), getDashboard(), getEcheancier()]);
      setEmps(e.employees);
      setDash(d);
      setEch(k.echeances);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function add() {
    if (!form.matricule || !form.nom_complet) return;
    try { await createEmployee(form); setForm({ ...EMPTY }); await refresh(); }
    catch { setErr("Création impossible (backend/DB)."); }
  }
  async function del(id: string) { try { await deleteEmployee(id); await refresh(); } catch { setErr("Suppression impossible."); } }

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={Users} title="RH — SIRH de pilotage" subtitle="Registre du personnel + tableau de bord + échéancier (déterministe)." />

      <div className="flex gap-2">
        <TabBtn active={tab === "registre"} onClick={() => setTab("registre")} icon={LayoutGrid} label="Registre" />
        <TabBtn active={tab === "dashboard"} onClick={() => setTab("dashboard")} icon={BarChart3} label="Tableau de bord" />
        <TabBtn active={tab === "echeancier"} onClick={() => setTab("echeancier")} icon={CalendarClock} label={`Échéancier${ech.length ? ` (${ech.length})` : ""}`} />
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {tab === "registre" && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Ajouter un employé</h2>
          <div className="mb-3 grid grid-cols-[80px_1fr_60px_120px_1fr_110px_36px] gap-2">
            <Inp value={form.matricule} onChange={(v) => setForm({ ...form, matricule: v })} placeholder="Mat." />
            <Inp value={form.nom_complet} onChange={(v) => setForm({ ...form, nom_complet: v })} placeholder="Nom" />
            <select value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} className="rounded-lg border border-black/10 bg-white px-1 text-sm">
              <option>H</option><option>F</option><option>NC</option>
            </select>
            <Inp value={form.date_embauche} type="date" onChange={(v) => setForm({ ...form, date_embauche: v })} />
            <Inp value={form.departement} onChange={(v) => setForm({ ...form, departement: v })} placeholder="Département" />
            <Inp value={form.salaire_base_xaf} type="number" onChange={(v) => setForm({ ...form, salaire_base_xaf: v })} placeholder="Salaire" />
            <button onClick={add} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {emps.length === 0 && <p className="text-sm text-muted">Aucun employé. Ajoutez-en un.</p>}
          {emps.map((e) => (
            <div key={e.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{e.matricule}</b> · {e.nom_complet} <span className="text-muted">· {e.departement || "—"}</span></span>
              <span className="flex items-center gap-3 text-muted">
                {fmtXaf(e.salaire_base_xaf)}
                <span className={"rounded-full px-2 py-0.5 text-xs " + (e.statut === "actif" ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-600")}>{e.statut}</span>
                <button onClick={() => del(e.id)} className="hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
              </span>
            </div>
          ))}
        </Card>
      )}

      {tab === "dashboard" && dash && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi label="Effectif" value={String(dash.effectif)} />
            <Kpi label="ETP" value={dash.etp} />
            <Kpi label="Masse salariale" value={fmtXaf(dash.masse_salariale_xaf)} />
            <Kpi label="Salaire moyen" value={fmtXaf(dash.salaire_moyen_xaf)} />
            <Kpi label="Turnover" value={dash.turnover_pct + " %"} />
            <Kpi label="Absentéisme" value={dash.absenteisme_pct + " %"} />
            <Kpi label="Ancienneté moy." value={dash.anciennete_moyenne_annees + " ans"} />
            <Kpi label="Écart salarial H/F" value={dash.ecart_salarial_hf_pct + " %"} />
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <Repartition title="Par genre" data={dash.repartition_genre} />
            <Repartition title="Par département" data={dash.par_departement} />
            <Repartition title="Pyramide des âges" data={dash.pyramide_ages} />
          </div>
        </>
      )}
      {tab === "dashboard" && !dash && !err && <Card><p className="text-sm text-muted">Aucune donnée. Ajoutez des employés.</p></Card>}

      {tab === "echeancier" && (
        <Card>
          {ech.length === 0 && <p className="text-sm text-muted">Aucune échéance dans l'horizon.</p>}
          {ech.map((e, i) => (
            <div key={i} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span className="flex items-center gap-2"><Urg level={e.urgence} /> {e.libelle}</span>
              <span className="text-muted">{e.date_cible} · {e.jours_restants < 0 ? `${-e.jours_restants} j de retard` : `dans ${e.jours_restants} j`}</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof Users; label: string }) {
  return (
    <button onClick={onClick} className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition", active ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <Card><div className="text-xs text-muted">{label}</div><div className="mt-1 text-lg font-semibold">{value}</div></Card>;
}

function Repartition({ title, data }: { title: string; data: Record<string, number> }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
  return (
    <Card>
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      {Object.keys(data).length === 0 && <p className="text-xs text-muted">—</p>}
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="mb-1.5">
          <div className="flex justify-between text-xs"><span>{k}</span><span className="text-muted">{v}</span></div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-black/10">
            <div className="h-full rounded-full bg-primary" style={{ width: `${(v / total) * 100}%` }} />
          </div>
        </div>
      ))}
    </Card>
  );
}
