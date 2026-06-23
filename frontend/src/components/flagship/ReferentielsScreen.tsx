"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Network, Briefcase, Grid3x3, Plus, AlertTriangle } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  listJobRoles, createJobRole, listSkills, createSkill, setEmployeeSkill, getMatrix, getGpec,
  type JobRole, type Skill, type Matrix, type Gpec,
} from "@/lib/gpec";

type Tab = "rme" | "rmc" | "matrice";

export function ReferentielsScreen() {
  const [tab, setTab] = useState<Tab>("rme");
  const [roles, setRoles] = useState<JobRole[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [matrix, setMatrix] = useState<Matrix | null>(null);
  const [gpec, setGpec] = useState<Gpec | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [rForm, setRForm] = useState({ code_emploi: "", intitule: "", famille_professionnelle: "" });
  const [sForm, setSForm] = useState({ code_competence: "", intitule: "", domaine: "technique" });

  const refresh = useCallback(async () => {
    setErr(null);
    try {
      const [r, s, m, g] = await Promise.all([listJobRoles(), listSkills(), getMatrix(), getGpec()]);
      setRoles(r.job_roles); setSkills(s.skills); setMatrix(m); setGpec(g);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function addRole() {
    if (!rForm.code_emploi || !rForm.intitule) return;
    try { await createJobRole({ ...rForm, activites: [], kpis: [] }); setRForm({ code_emploi: "", intitule: "", famille_professionnelle: "" }); await refresh(); }
    catch { setErr("Création impossible (backend/DB)."); }
  }
  async function addSkill() {
    if (!sForm.code_competence || !sForm.intitule) return;
    try { await createSkill(sForm); setSForm({ code_competence: "", intitule: "", domaine: "technique" }); await refresh(); }
    catch { setErr("Création impossible (backend/DB)."); }
  }
  async function note(matricule: string, code: string, value: number) {
    try { await setEmployeeSkill({ employee_matricule: matricule, code_competence: code, note: value }); await refresh(); }
    catch { setErr("Notation impossible."); }
  }

  const crit = new Set(gpec?.competences_critiques.map((c) => c.code_competence) ?? []);
  const couv = new Map(gpec?.par_employe.map((e) => [e.matricule, e.couverture_pct]) ?? []);

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={Network} title="Référentiels & GPEC" subtitle="Emplois (RME) · Compétences (RMC) · Matrice de compétences + écarts (déterministe)." />

      <div className="flex gap-2">
        <TabBtn active={tab === "rme"} onClick={() => setTab("rme")} icon={Briefcase} label="RME — Emplois" />
        <TabBtn active={tab === "rmc"} onClick={() => setTab("rmc")} icon={Grid3x3} label="RMC — Compétences" />
        <TabBtn active={tab === "matrice"} onClick={() => setTab("matrice")} icon={Network} label="Matrice + GPEC" />
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {tab === "rme" && (
        <Card>
          <div className="mb-3 grid grid-cols-[110px_1fr_1fr_36px] gap-2">
            <Inp value={rForm.code_emploi} onChange={(v) => setRForm({ ...rForm, code_emploi: v })} placeholder="Code" />
            <Inp value={rForm.intitule} onChange={(v) => setRForm({ ...rForm, intitule: v })} placeholder="Intitulé emploi-repère" />
            <Inp value={rForm.famille_professionnelle} onChange={(v) => setRForm({ ...rForm, famille_professionnelle: v })} placeholder="Famille" />
            <button onClick={addRole} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {roles.length === 0 && <p className="text-sm text-muted">Aucun emploi. Ajoutez-en un.</p>}
          {roles.map((r) => (
            <div key={r.id} className="border-b border-black/5 py-1.5 text-sm last:border-0">
              <b>{r.code_emploi}</b> · {r.intitule} <span className="text-muted">· {r.famille_professionnelle || "—"}</span>
            </div>
          ))}
        </Card>
      )}

      {tab === "rmc" && (
        <Card>
          <div className="mb-3 grid grid-cols-[110px_1fr_130px_36px] gap-2">
            <Inp value={sForm.code_competence} onChange={(v) => setSForm({ ...sForm, code_competence: v })} placeholder="Code" />
            <Inp value={sForm.intitule} onChange={(v) => setSForm({ ...sForm, intitule: v })} placeholder="Intitulé compétence" />
            <select value={sForm.domaine} onChange={(e) => setSForm({ ...sForm, domaine: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 text-sm">
              <option value="technique">Technique</option><option value="transversal">Transversal</option><option value="soft">Soft skills</option>
            </select>
            <button onClick={addSkill} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {skills.length === 0 && <p className="text-sm text-muted">Aucune compétence. Ajoutez-en une.</p>}
          {skills.map((s) => (
            <div key={s.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{s.code_competence}</b> · {s.intitule}</span>
              <span className="flex items-center gap-2 text-xs text-muted">
                {s.domaine}
                {crit.has(s.code_competence) && <span className="flex items-center gap-1 text-amber-700"><AlertTriangle className="h-3 w-3" /> critique</span>}
              </span>
            </div>
          ))}
        </Card>
      )}

      {tab === "matrice" && (
        <Card className="overflow-x-auto">
          {!matrix || matrix.lignes.length === 0 || matrix.competences.length === 0 ? (
            <p className="text-sm text-muted">Ajoutez des employés (Registre RH) et des compétences (RMC) pour remplir la matrice.</p>
          ) : (
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  <th className="sticky left-0 bg-surface px-2 py-1 text-left">Collaborateur</th>
                  <th className="px-2 py-1 text-left">Emploi</th>
                  <th className="px-2 py-1 text-right">Couv.</th>
                  {matrix.competences.map((c) => (
                    <th key={c} className={"px-2 py-1 text-center " + (crit.has(c) ? "text-amber-700" : "")}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrix.lignes.map((row) => (
                  <tr key={row.matricule} className="border-t border-black/5">
                    <td className="sticky left-0 bg-surface px-2 py-1 font-medium">{row.matricule} · {row.nom_complet}</td>
                    <td className="px-2 py-1 text-muted">{row.code_emploi ?? "—"}</td>
                    <td className="px-2 py-1 text-right text-muted">{couv.get(row.matricule) ?? "—"}%</td>
                    {matrix.competences.map((c) => (
                      <td key={c} className="px-1 py-1 text-center">
                        <select
                          value={row.notes[c] ?? 0}
                          onChange={(e) => note(row.matricule, c, Number(e.target.value))}
                          className={"w-12 rounded border border-black/10 bg-white text-center text-xs " + noteColor(row.notes[c] ?? 0)}
                        >
                          {[0, 1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
                        </select>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="mt-3 text-xs text-muted">Note 0 (aucune) → 4 (expert). Couv. = taux de couverture GPEC (détenu vs requis). Compétences en jaune = sans expert (risque clé).</p>
        </Card>
      )}
    </div>
  );
}

function noteColor(n: number): string {
  if (n >= 4) return "text-emerald-700";
  if (n >= 2) return "text-ink";
  if (n === 1) return "text-amber-700";
  return "text-muted";
}

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof Network; label: string }) {
  return (
    <button onClick={onClick} className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition", active ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}
