"use client";

import { useCallback, useEffect, useState } from "react";
import { Handshake, Plus, Trash2 } from "lucide-react";
import { Card, Button, SeverityBadge, Skeleton } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { ApiError } from "@/lib/api";
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

export function ProjetsOngScreen() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [ventilation, setVentilation] = useState<Ventilation | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [budgetLines, setBudgetLines] = useState<BudgetLine[]>([]);
  const [suivi, setSuivi] = useState<Suivi | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [pForm, setPForm] = useState({ intitule: "", bailleur: "", budget_total: "", devise: "XAF", date_debut: TODAY });
  const [lForm, setLForm] = useState({ rubrique: "", activite: "", montant_prevu: "" });

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
    try {
      await createProject({
        intitule: pForm.intitule,
        bailleur: pForm.bailleur,
        budget_total: pForm.budget_total,
        devise: pForm.devise || "XAF",
        date_debut: pForm.date_debut || null,
      });
      setPForm({ intitule: "", bailleur: "", budget_total: "", devise: "XAF", date_debut: TODAY });
      await refresh();
    } catch {
      setErr("Création du projet impossible (backend/DB).");
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
          <div className="mb-2 grid grid-cols-2 gap-2">
            <Inp value={pForm.intitule} onChange={(v) => setPForm({ ...pForm, intitule: v })} placeholder="Intitulé" />
            <Inp value={pForm.bailleur} onChange={(v) => setPForm({ ...pForm, bailleur: v })} placeholder="Bailleur" />
            <Inp value={pForm.budget_total} type="number" onChange={(v) => setPForm({ ...pForm, budget_total: v })} placeholder="Budget total" />
            <Inp value={pForm.devise} onChange={(v) => setPForm({ ...pForm, devise: v })} placeholder="Devise" />
            <Inp value={pForm.date_debut} type="date" onChange={(v) => setPForm({ ...pForm, date_debut: v })} />
            <button onClick={addProject} className="flex items-center justify-center gap-1 rounded-lg bg-forest text-white"><Plus className="h-4 w-4" /> Ajouter</button>
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
                  {montant(p.budget_total, p.devise)} · {STATUTS.find((s) => s.value === p.statut)?.label ?? p.statut}
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
