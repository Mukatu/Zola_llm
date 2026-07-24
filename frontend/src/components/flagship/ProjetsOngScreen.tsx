"use client";

import { useCallback, useEffect, useState } from "react";
import { Handshake, Plus, Trash2 } from "lucide-react";
import { Card, Button, SeverityBadge, Skeleton } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { fmt } from "@/lib/data";
import { fmtXaf } from "@/lib/erp";
import { ApiError } from "@/lib/api";
import { getFxRates, type FxRate } from "@/lib/fx";
import {
  listProjects,
  createProject,
  deleteProject,
  listBudgetLines,
  createBudgetLine,
  deleteBudgetLine,
  getSuivi,
  getVentilation,
  type Project,
  type BudgetLine,
  type Suivi,
  type Ventilation,
  type StatutProjet,
} from "@/lib/projets";

const TODAY = new Date().toISOString().slice(0, 10);

const STATUTS: { value: StatutProjet; label: string }[] = [
  { value: "en_cours", label: "En cours" },
  { value: "suspendu", label: "Suspendu" },
  { value: "clos", label: "Clos" },
];

// Formatage montant (+ devise optionnelle) — les montants voyagent en string décimale depuis l'API.
function montant(v: string, devise = ""): string {
  const n = Number(v);
  const s = Number.isFinite(n) ? n.toLocaleString("fr-FR") : v;
  return devise ? `${s} ${devise}` : s;
}

// Traduit les codes d'erreur backend en messages FR sobres (même contrat que le Registre / factures).
function fxError(e: unknown): string {
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

export function ProjetsOngScreen() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [ventilation, setVentilation] = useState<Ventilation | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [budgetLines, setBudgetLines] = useState<BudgetLine[]>([]);
  const [suivi, setSuivi] = useState<Suivi | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [rates, setRates] = useState<FxRate[]>([]);

  const [pForm, setPForm] = useState({ intitule: "", bailleur: "", budget_total: "", devise: "XAF", date_debut: TODAY });
  const [lForm, setLForm] = useState({ rubrique: "", activite: "", montant_prevu: "" });

  const selRateP = rates.find((r) => r.devise === pForm.devise);
  const enDeviseP = pForm.devise !== "XAF";
  const apercuXafP =
    enDeviseP && pForm.budget_total && selRateP?.taux_vers_xaf
      ? Number(pForm.budget_total) * Number(selRateP.taux_vers_xaf)
      : null;

  const refresh = useCallback(async () => {
    try {
      const [p, v] = await Promise.all([listProjects(), getVentilation()]);
      setProjects(p.projects);
      setVentilation(v);
      setErr(null);
    } catch (er) {
      setErr(er instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    getFxRates().then((v) => setRates(v.rates)).catch(() => setRates([]));
  }, [refresh]);

  const refreshDetail = useCallback(async (projectId: string) => {
    setDetailLoading(true);
    try {
      const [l, s] = await Promise.all([listBudgetLines(projectId), getSuivi(projectId)]);
      setBudgetLines(l.budget_lines);
      setSuivi(s);
      setErr(null);
    } catch {
      setErr("Suivi du projet indisponible.");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) refreshDetail(selectedId);
    else {
      setBudgetLines([]);
      setSuivi(null);
    }
  }, [selectedId, refreshDetail]);

  const selected = projects.find((p) => p.id === selectedId) ?? null;

  async function addProject() {
    if (!pForm.intitule || !pForm.bailleur || !pForm.budget_total) return;
    const base = { intitule: pForm.intitule, bailleur: pForm.bailleur, date_debut: pForm.date_debut || null };
    const payload = enDeviseP
      ? { ...base, devise: pForm.devise, budget_total_devise: pForm.budget_total }
      : { ...base, devise: pForm.devise || "XAF", budget_total: pForm.budget_total };
    try {
      await createProject(payload);
      setPForm({ intitule: "", bailleur: "", budget_total: "", devise: pForm.devise, date_debut: TODAY });
      setErr(null);
      await refresh();
    } catch (e) {
      setErr(fxError(e));
    }
  }
  async function removeProject(id: string) {
    try {
      await deleteProject(id);
      if (selectedId === id) setSelectedId(null);
      await refresh();
    } catch {
      setErr("Suppression du projet impossible.");
    }
  }
  async function addBudgetLine() {
    if (!selectedId || !lForm.rubrique || !lForm.montant_prevu) return;
    try {
      await createBudgetLine({
        project_id: selectedId,
        rubrique: lForm.rubrique,
        activite: lForm.activite || null,
        montant_prevu: lForm.montant_prevu,
      });
      setLForm({ rubrique: "", activite: "", montant_prevu: "" });
      await refreshDetail(selectedId);
    } catch {
      setErr("Création de la ligne budgétaire impossible.");
    }
  }
  async function removeBudgetLine(id: string) {
    if (!selectedId) return;
    try {
      await deleteBudgetLine(id);
      await refreshDetail(selectedId);
    } catch {
      setErr("Suppression de la ligne budgétaire impossible.");
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <FlagshipHeader
        icon={Handshake}
        title="Projets ONG"
        subtitle="Gestion financière des projets bailleur : lignes budgétaires, suivi d'exécution, ventilation — persistant."
      />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {/* Ventilation par bailleur — agrégat global, indépendant du projet sélectionné */}
      <Card>
        <h2 className="mb-2 text-sm font-semibold">Ventilation par bailleur</h2>
        {loading ? (
          <Skeleton className="h-4 w-full" />
        ) : !ventilation || Object.keys(ventilation).length === 0 ? (
          <p className="text-sm text-muted">Aucune donnée de ventilation.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(ventilation).map(([bailleur, v]) => (
              <div key={bailleur} className="rounded-xl bg-mint/10 p-3">
                <p className="text-sm font-semibold">{bailleur}</p>
                <p className="text-xs text-muted">Budget : {montant(v.budget_total)}</p>
                <p className="text-xs text-muted">Réalisé : {montant(v.realise)} ({v.taux.toFixed(0)} %)</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Liste des projets + création */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Projets</h2>
          <div className="mb-1 grid grid-cols-2 gap-2">
            <Inp value={pForm.intitule} onChange={(v) => setPForm({ ...pForm, intitule: v })} placeholder="Intitulé" />
            <Inp value={pForm.bailleur} onChange={(v) => setPForm({ ...pForm, bailleur: v })} placeholder="Bailleur" />
            <Inp
              value={pForm.budget_total}
              type="number"
              onChange={(v) => setPForm({ ...pForm, budget_total: v })}
              placeholder={enDeviseP ? `Budget total ${pForm.devise}` : "Budget total"}
            />
            <select
              value={pForm.devise}
              onChange={(e) => setPForm({ ...pForm, devise: e.target.value })}
              className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            >
              {(rates.length ? rates : [{ devise: "XAF" } as FxRate]).map((r) => (
                <option key={r.devise} value={r.devise}>{r.devise}</option>
              ))}
            </select>
            <Inp value={pForm.date_debut} type="date" onChange={(v) => setPForm({ ...pForm, date_debut: v })} />
            <button onClick={addProject} className="flex items-center justify-center gap-1 rounded-lg bg-forest text-white"><Plus className="h-4 w-4" /> Ajouter</button>
          </div>
          <div className="mb-2 min-h-[1rem] text-xs">
            {enDeviseP && apercuXafP !== null && (
              <span className="text-muted">≈ {fmtXaf(String(Math.round(apercuXafP)))} au taux {fmt(selRateP?.taux_vers_xaf ?? "0")}</span>
            )}
            {enDeviseP && selRateP && !selRateP.validated && (
              <span className="text-amber-700">Taux {pForm.devise} non validé — à saisir/valider dans « Devises / Change ».</span>
            )}
          </div>

          {loading ? (
            <Skeleton className="h-10 w-full" />
          ) : projects.length === 0 ? (
            <p className="text-sm text-muted">Aucun projet enregistré.</p>
          ) : (
            projects.map((p) => (
              <div
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={
                  "flex cursor-pointer items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0 " +
                  (p.id === selectedId ? "font-semibold text-forest" : "")
                }
              >
                <span>
                  {p.intitule} <span className="text-xs text-muted">({p.bailleur})</span>
                </span>
                <span className="flex items-center gap-2 text-muted">
                  <span>
                    {p.budget_total_devise && p.devise !== "XAF" && (
                      <span className="mr-1 text-[11px]">{fmt(p.budget_total_devise)} {p.devise} →</span>
                    )}
                    {fmtXaf(p.budget_total)}
                  </span>
                  · {STATUTS.find((s) => s.value === p.statut)?.label ?? p.statut}
                  <button onClick={(e) => { e.stopPropagation(); removeProject(p.id); }} className="text-muted hover:text-red-600">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </span>
              </div>
            ))
          )}
        </Card>

        {/* Détail projet : lignes budgétaires + suivi d'exécution */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">
            {selected ? `Suivi — ${selected.intitule}` : "Suivi d'exécution"}
          </h2>
          {!selected && <p className="text-sm text-muted">Sélectionnez un projet pour voir son suivi.</p>}

          {selected && detailLoading && (
            <>
              <Skeleton className="mb-2 h-4 w-1/2" />
              <Skeleton className="h-4 w-full" />
            </>
          )}

          {selected && !detailLoading && (
            <div className="flex flex-col gap-3">
              <div className="mb-1 grid grid-cols-3 gap-2">
                <Inp value={lForm.rubrique} onChange={(v) => setLForm({ ...lForm, rubrique: v })} placeholder="Rubrique" />
                <Inp value={lForm.activite} onChange={(v) => setLForm({ ...lForm, activite: v })} placeholder="Activité" />
                <div className="flex gap-1">
                  <Inp value={lForm.montant_prevu} type="number" onChange={(v) => setLForm({ ...lForm, montant_prevu: v })} placeholder="Prévu" />
                  <button onClick={addBudgetLine} className="grid place-items-center rounded-lg bg-forest px-2 text-white"><Plus className="h-4 w-4" /></button>
                </div>
              </div>

              {budgetLines.map((l) => (
                <div key={l.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
                  <span>
                    <b>{l.rubrique}</b> {l.activite && <span className="text-xs text-muted">({l.activite})</span>}
                    {!l.eligible && <span className="ml-1 text-xs text-amber-700">non éligible</span>}
                  </span>
                  <span className="flex items-center gap-2 text-muted">
                    {montant(l.montant_realise, selected.devise)} / {montant(l.montant_prevu, selected.devise)}
                    <button onClick={() => removeBudgetLine(l.id)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
                  </span>
                </div>
              ))}

              {suivi && (
                <div className="mt-2 flex flex-col gap-2 rounded-xl bg-black/[0.02] p-3">
                  <p className="text-sm font-semibold">Exécution par rubrique</p>
                  {suivi.par_rubrique.map((r) => (
                    <div key={r.rubrique} className="flex items-center justify-between text-sm">
                      <span>{r.rubrique}</span>
                      <span className="flex items-center gap-2">
                        {r.taux_execution.toFixed(0)} % réalisé · {r.taux_engagement.toFixed(0)} % engagé
                        {r.depassement && <SeverityBadge level="critical" />}
                      </span>
                    </div>
                  ))}
                  <div className="mt-1 border-t border-black/10 pt-2 text-sm">
                    <p>Taux global : <b>{suivi.totaux.taux_global.toFixed(0)} %</b></p>
                    <p>Réalisé éligible : {montant(suivi.totaux.realise_eligible, selected.devise)} / total {montant(suivi.totaux.realise_total, selected.devise)}</p>
                    <p>Reste à réaliser : {montant(suivi.totaux.reste_a_realiser, selected.devise)}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
