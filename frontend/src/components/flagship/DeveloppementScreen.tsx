"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { GraduationCap, Plus, CheckCircle2, BookOpen, Star, AlertTriangle, TrendingUp } from "lucide-react";
import { Card } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { fmtXaf } from "@/lib/erp";
import { ApiError } from "@/lib/api";
import {
  listTrainings, createTraining, listSessions, createSession,
  listEnrollments, createEnrollment, patchEnrollment, getFormationDashboard,
  createEvaluation, getTalentReview, getPlanFormation, getGpecRisks,
  type Training, type Session, type Enrollment, type FormationDashboard,
  type TalentReview, type PlanFormation, type GpecRisks,
} from "@/lib/formation";

type Tab = "formation" | "evaluations" | "gpec";
const NIVEAUX = ["haut", "moyen", "bas"]; // lignes (perf) du haut vers le bas
const POTS = ["bas", "moyen", "haut"]; // colonnes (potentiel)

export function DeveloppementScreen() {
  const [tab, setTab] = useState<Tab>("formation");
  const [trainings, setTrainings] = useState<Training[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [enrolls, setEnrolls] = useState<Enrollment[]>([]);
  const [dash, setDash] = useState<FormationDashboard | null>(null);
  const [review, setReview] = useState<TalentReview | null>(null);
  const [plan, setPlan] = useState<PlanFormation | null>(null);
  const [risks, setRisks] = useState<GpecRisks | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [tForm, setTForm] = useState({ code: "", intitule: "", duree_heures: "0", cout_xaf: "0" });
  const [sForm, setSForm] = useState({ training_code: "", date_debut: "2026-07-01" });
  const [eForm, setEForm] = useState({ session_id: "", employee_matricule: "" });
  const [vForm, setVForm] = useState({ employee_matricule: "", periode: "2026", performance: 3, potentiel: 3 });

  const refresh = useCallback(async () => {
    setErr(null);
    try {
      const [t, s, e, d, r, p, k] = await Promise.all([
        listTrainings(), listSessions(), listEnrollments(), getFormationDashboard(),
        getTalentReview(), getPlanFormation(), getGpecRisks(),
      ]);
      setTrainings(t.trainings); setSessions(s.sessions); setEnrolls(e.enrollments); setDash(d);
      setReview(r); setPlan(p); setRisks(k);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function addT() { if (!tForm.code || !tForm.intitule) return; try { await createTraining(tForm); setTForm({ code: "", intitule: "", duree_heures: "0", cout_xaf: "0" }); await refresh(); } catch { setErr("Création impossible."); } }
  async function addS() { if (!sForm.training_code) return; try { await createSession(sForm); setSForm({ training_code: "", date_debut: sForm.date_debut }); await refresh(); } catch { setErr("Création impossible."); } }
  async function addE() { if (!eForm.session_id || !eForm.employee_matricule) return; try { await createEnrollment(eForm); setEForm({ session_id: "", employee_matricule: "" }); await refresh(); } catch { setErr("Inscription impossible."); } }
  async function realise(id: string) { try { await patchEnrollment(id, "realise"); await refresh(); } catch { setErr("Action impossible."); } }
  async function addV() { if (!vForm.employee_matricule) return; try { await createEvaluation(vForm); setVForm({ ...vForm, employee_matricule: "" }); await refresh(); } catch { setErr("Évaluation impossible."); } }

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={GraduationCap} title="Développement RH" subtitle="Formation · Évaluations (9-box) · GPEC (déterministe)." />

      <div className="flex gap-2">
        <TabBtn active={tab === "formation"} onClick={() => setTab("formation")} icon={BookOpen} label="Formation" />
        <TabBtn active={tab === "evaluations"} onClick={() => setTab("evaluations")} icon={Star} label="Évaluations" />
        <TabBtn active={tab === "gpec"} onClick={() => setTab("gpec")} icon={TrendingUp} label="GPEC" />
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {tab === "formation" && (
        <>
          {dash && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Kpi label="Taux de réalisation" value={dash.taux_realisation_pct + " %"} />
              <Kpi label="Coût / employé" value={fmtXaf(dash.cout_par_employe_xaf)} />
              <Kpi label="Heures / employé" value={dash.heures_par_employe} />
              <Kpi label="Satisfaction (chaud)" value={dash.satisfaction_moyenne + " /5"} />
            </div>
          )}
          <Card>
            <h2 className="mb-2 text-sm font-semibold">Catalogue de formations</h2>
            <div className="mb-3 grid grid-cols-[90px_1fr_70px_110px_36px] gap-2">
              <Inp value={tForm.code} onChange={(v) => setTForm({ ...tForm, code: v })} placeholder="Code" />
              <Inp value={tForm.intitule} onChange={(v) => setTForm({ ...tForm, intitule: v })} placeholder="Intitulé" />
              <Inp value={tForm.duree_heures} type="number" onChange={(v) => setTForm({ ...tForm, duree_heures: v })} placeholder="Heures" />
              <Inp value={tForm.cout_xaf} type="number" onChange={(v) => setTForm({ ...tForm, cout_xaf: v })} placeholder="Coût" />
              <button onClick={addT} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
            </div>
            {trainings.map((t) => (
              <div key={t.id} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
                <span><b>{t.code}</b> · {t.intitule}</span>
                <span className="text-muted">{t.duree_heures} h · {fmtXaf(t.cout_xaf)}</span>
              </div>
            ))}
          </Card>
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <h2 className="mb-2 text-sm font-semibold">Sessions</h2>
              <div className="mb-3 grid grid-cols-[1fr_130px_36px] gap-2">
                <select value={sForm.training_code} onChange={(e) => setSForm({ ...sForm, training_code: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 text-sm">
                  <option value="">Formation…</option>
                  {trainings.map((t) => <option key={t.id} value={t.code}>{t.code}</option>)}
                </select>
                <Inp value={sForm.date_debut} type="date" onChange={(v) => setSForm({ ...sForm, date_debut: v })} />
                <button onClick={addS} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
              </div>
              {sessions.map((s) => (
                <div key={s.id} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
                  <span><b>{s.training_code}</b> · {s.date_debut}</span>
                  <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs text-muted">{s.statut}</span>
                </div>
              ))}
            </Card>
            <Card>
              <h2 className="mb-2 text-sm font-semibold">Inscriptions</h2>
              <div className="mb-3 grid grid-cols-[1fr_100px_36px] gap-2">
                <select value={eForm.session_id} onChange={(e) => setEForm({ ...eForm, session_id: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 text-sm">
                  <option value="">Session…</option>
                  {sessions.map((s) => <option key={s.id} value={s.id}>{s.training_code} · {s.date_debut}</option>)}
                </select>
                <Inp value={eForm.employee_matricule} onChange={(v) => setEForm({ ...eForm, employee_matricule: v })} placeholder="Matricule" />
                <button onClick={addE} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
              </div>
              {enrolls.map((en) => (
                <div key={en.id} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
                  <span>{en.employee_matricule}</span>
                  <span className="flex items-center gap-2">
                    <span className={"rounded-full px-2 py-0.5 text-xs " + (en.statut === "realise" ? "bg-emerald-100 text-emerald-700" : "bg-black/5 text-muted")}>{en.statut}</span>
                    {en.statut !== "realise" && <button onClick={() => realise(en.id)} title="Marquer réalisé" className="text-emerald-600 hover:text-emerald-800"><CheckCircle2 className="h-4 w-4" /></button>}
                  </span>
                </div>
              ))}
            </Card>
          </div>
        </>
      )}

      {tab === "evaluations" && (
        <>
          <Card>
            <h2 className="mb-2 text-sm font-semibold">Nouvelle évaluation</h2>
            <div className="grid grid-cols-[1fr_90px_120px_120px_36px] gap-2">
              <Inp value={vForm.employee_matricule} onChange={(v) => setVForm({ ...vForm, employee_matricule: v })} placeholder="Matricule" />
              <Inp value={vForm.periode} onChange={(v) => setVForm({ ...vForm, periode: v })} placeholder="Période" />
              <Score label="Perf." value={vForm.performance} onChange={(n) => setVForm({ ...vForm, performance: n })} />
              <Score label="Potentiel" value={vForm.potentiel} onChange={(n) => setVForm({ ...vForm, potentiel: n })} />
              <button onClick={addV} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
            </div>
          </Card>
          {review && (
            <Card>
              <h2 className="mb-2 text-sm font-semibold">Matrice 9-box (performance × potentiel)</h2>
              <div className="grid grid-cols-[60px_1fr_1fr_1fr] gap-1 text-xs">
                <div />
                {POTS.map((p) => <div key={p} className="text-center font-medium text-muted">Pot. {p}</div>)}
                {NIVEAUX.map((perf) => (
                  <FragmentRow key={perf} perf={perf} pots={POTS} grid={review.grid} />
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-3 text-sm">
                <span className="flex items-center gap-1"><Star className="h-4 w-4 text-amber-500" /> Top talents : <b>{review.top_talents.join(", ") || "—"}</b></span>
                <span className="text-muted">Sous-performeurs : {review.sous_performeurs.join(", ") || "—"}</span>
              </div>
            </Card>
          )}
        </>
      )}

      {tab === "gpec" && (
        <>
          <Card>
            <h2 className="mb-2 text-sm font-semibold">Plan de formation suggéré (depuis les écarts)</h2>
            {(!plan || plan.suggestions.length === 0) && <p className="text-sm text-muted">Aucun écart — ou matrice/profils non renseignés.</p>}
            {plan?.suggestions.map((s, i) => (
              <div key={i} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
                <span>{s.matricule} · <b>{s.code_competence}</b> (écart {s.ecart})</span>
                <span className="text-muted">{s.formations.length ? "→ " + s.formations.join(", ") : "aucune formation au catalogue"}</span>
              </div>
            ))}
          </Card>
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><AlertTriangle className="h-4 w-4 text-red-600" /> Risques</h3>
              {(!risks || risks.risques.length === 0) && <p className="text-sm text-muted">Aucun risque détecté.</p>}
              {risks?.risques.map((r, i) => (
                <div key={i} className="border-b border-black/5 py-1 text-sm last:border-0">
                  <span className="rounded bg-red-100 px-1.5 text-xs text-red-700">{r.type}</span>{" "}
                  {r.code_competence ?? r.matricule}{r.age ? ` (${r.age} ans)` : ""}
                </div>
              ))}
            </Card>
            <Card>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><TrendingUp className="h-4 w-4 text-emerald-600" /> Opportunités</h3>
              {(!risks || risks.opportunites.length === 0) && <p className="text-sm text-muted">—</p>}
              {risks?.opportunites.map((o, i) => (
                <div key={i} className="border-b border-black/5 py-1 text-sm last:border-0">
                  <span className="rounded bg-emerald-100 px-1.5 text-xs text-emerald-700">{o.type}</span>{" "}
                  {o.matricule ?? o.code_competence}{o.experts ? ` (${o.experts} experts)` : ""}
                </div>
              ))}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function FragmentRow({ perf, pots, grid }: { perf: string; pots: string[]; grid: Record<string, string[]> }) {
  return (
    <>
      <div className="flex items-center justify-end pr-1 font-medium text-muted">Perf. {perf}</div>
      {pots.map((pot) => {
        const cell = grid[`${perf}/${pot}`] ?? [];
        const hot = perf === "haut" && pot === "haut";
        return (
          <div key={pot} className={clsx("min-h-12 rounded-lg p-1.5", hot ? "bg-emerald-100" : "bg-black/[0.03]")}>
            {cell.map((m) => <span key={m} className="mr-1 inline-block rounded bg-surface px-1 text-xs shadow-sm">{m}</span>)}
          </div>
        );
      })}
    </>
  );
}

function Score({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  return (
    <label className="flex items-center gap-1 text-xs text-muted">
      {label}
      <select value={value} onChange={(e) => onChange(Number(e.target.value))} className="rounded-lg border border-black/10 bg-white px-1 py-1 text-sm text-ink">
        {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
      </select>
    </label>
  );
}

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof GraduationCap; label: string }) {
  return (
    <button onClick={onClick} className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition", active ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <Card><div className="text-xs text-muted">{label}</div><div className="mt-1 text-lg font-semibold">{value}</div></Card>;
}
