"use client";

import { useCallback, useEffect, useState } from "react";
import { GraduationCap, Plus, CheckCircle2 } from "lucide-react";
import { Card } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { fmtXaf } from "@/lib/erp";
import { ApiError } from "@/lib/api";
import {
  listTrainings, createTraining, listSessions, createSession,
  listEnrollments, createEnrollment, patchEnrollment, getFormationDashboard,
  type Training, type Session, type Enrollment, type FormationDashboard,
} from "@/lib/formation";

export function DeveloppementScreen() {
  const [trainings, setTrainings] = useState<Training[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [enrolls, setEnrolls] = useState<Enrollment[]>([]);
  const [dash, setDash] = useState<FormationDashboard | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [tForm, setTForm] = useState({ code: "", intitule: "", duree_heures: "0", cout_xaf: "0" });
  const [sForm, setSForm] = useState({ training_code: "", date_debut: "2026-07-01" });
  const [eForm, setEForm] = useState({ session_id: "", employee_matricule: "" });

  const refresh = useCallback(async () => {
    setErr(null);
    try {
      const [t, s, e, d] = await Promise.all([listTrainings(), listSessions(), listEnrollments(), getFormationDashboard()]);
      setTrainings(t.trainings); setSessions(s.sessions); setEnrolls(e.enrollments); setDash(d);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function addT() { if (!tForm.code || !tForm.intitule) return; try { await createTraining(tForm); setTForm({ code: "", intitule: "", duree_heures: "0", cout_xaf: "0" }); await refresh(); } catch { setErr("Création impossible."); } }
  async function addS() { if (!sForm.training_code) return; try { await createSession(sForm); setSForm({ training_code: "", date_debut: sForm.date_debut }); await refresh(); } catch { setErr("Création impossible."); } }
  async function addE() { if (!eForm.session_id || !eForm.employee_matricule) return; try { await createEnrollment(eForm); setEForm({ session_id: "", employee_matricule: "" }); await refresh(); } catch { setErr("Inscription impossible."); } }
  async function realise(id: string) { try { await patchEnrollment(id, "realise"); await refresh(); } catch { setErr("Action impossible."); } }

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={GraduationCap} title="Développement RH — Formation" subtitle="Catalogue, sessions, inscriptions et indicateurs (déterministe)." />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

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
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <Card><div className="text-xs text-muted">{label}</div><div className="mt-1 text-lg font-semibold">{value}</div></Card>;
}
