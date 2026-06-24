"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { UserPlus, Briefcase, KanbanSquare, BarChart3, Plus, Sparkles, Save } from "lucide-react";
import { Card, Button, Skeleton } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { ApiError } from "@/lib/api";
import { runQuery } from "@/lib/query";
import { hrGeneratePrompt, createDocument } from "@/lib/documents";
import {
  ETAPES, listVacancies, createVacancy, listCandidates, createCandidate,
  listApplications, createApplication, moveApplication, getRecruitmentDashboard,
  type Vacancy, type Candidate, type Application, type RecruitmentDashboard,
} from "@/lib/recrutement";

type Tab = "vacances" | "pipeline" | "kpis" | "generation";

const GEN_TYPES = [
  { id: "fiche_poste", label: "Fiche de poste" },
  { id: "grille_entretien", label: "Grille d'entretien" },
  { id: "annonce", label: "Annonce" },
  { id: "plan_recrutement", label: "Plan de recrutement" },
];
const ALL_STAGES = [...ETAPES, "rejeté", "désisté"];

export function RecrutementScreen() {
  const [tab, setTab] = useState<Tab>("vacances");
  const [vacs, setVacs] = useState<Vacancy[]>([]);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [apps, setApps] = useState<Application[]>([]);
  const [dash, setDash] = useState<RecruitmentDashboard | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [vForm, setVForm] = useState({ code_vacance: "", intitule: "", date_ouverture: "2026-06-01", departement: "" });
  const [aForm, setAForm] = useState({ nom: "", source: "spontanee", code_vacance: "" });

  // Génération
  const [gType, setGType] = useState("fiche_poste");
  const [gEmploi, setGEmploi] = useState("");
  const [gTitre, setGTitre] = useState("");
  const [gDraft, setGDraft] = useState<string | null>(null);
  const [gLoading, setGLoading] = useState(false);
  const [gSaved, setGSaved] = useState(false);

  const refresh = useCallback(async () => {
    setErr(null);
    try {
      const [v, c, a, d] = await Promise.all([listVacancies(), listCandidates(), listApplications(), getRecruitmentDashboard()]);
      setVacs(v.vacancies); setCands(c.candidates); setApps(a.applications); setDash(d);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function addVac() {
    if (!vForm.code_vacance || !vForm.intitule) return;
    try { await createVacancy(vForm); setVForm({ code_vacance: "", intitule: "", date_ouverture: vForm.date_ouverture, departement: "" }); await refresh(); }
    catch { setErr("Création impossible (backend/DB)."); }
  }
  async function addApp() {
    if (!aForm.nom || !aForm.code_vacance) return;
    try {
      const c = await createCandidate({ nom: aForm.nom, source: aForm.source });
      await createApplication({ candidate_id: c.id, code_vacance: aForm.code_vacance, date_candidature: new Date().toISOString().slice(0, 10) });
      setAForm({ nom: "", source: aForm.source, code_vacance: aForm.code_vacance });
      await refresh();
    } catch { setErr("Ajout candidature impossible."); }
  }
  async function move(id: string, etape: string) {
    try { await moveApplication(id, etape); await refresh(); } catch { setErr("Déplacement impossible."); }
  }

  async function generate() {
    setGLoading(true); setErr(null); setGDraft(null); setGSaved(false);
    try {
      const { titre, prompt } = await hrGeneratePrompt({ type: gType, code_emploi: gEmploi || undefined });
      setGTitre(titre);
      const r = await runQuery(prompt);
      setGDraft(r.content);
    } catch (e) {
      setErr(e instanceof ApiError ? "Génération indisponible (LLM/auth requis ou backend)." : "Service indisponible.");
    } finally { setGLoading(false); }
  }
  async function saveDoc() {
    if (!gDraft) return;
    try { await createDocument({ type: gType, titre: gTitre, contenu: gDraft, source_ref: gEmploi || undefined }); setGSaved(true); }
    catch { setErr("Enregistrement impossible (backend/DB)."); }
  }

  const nameOf = new Map(cands.map((c) => [c.id, `${c.prenom} ${c.nom}`.trim()]));

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={UserPlus} title="Recrutement" subtitle="Vacances · pipeline de candidatures · indicateurs (entonnoir, time-to-hire)." />

      <div className="flex gap-2">
        <TabBtn active={tab === "vacances"} onClick={() => setTab("vacances")} icon={Briefcase} label="Vacances" />
        <TabBtn active={tab === "pipeline"} onClick={() => setTab("pipeline")} icon={KanbanSquare} label="Pipeline" />
        <TabBtn active={tab === "kpis"} onClick={() => setTab("kpis")} icon={BarChart3} label="Indicateurs" />
        <TabBtn active={tab === "generation"} onClick={() => setTab("generation")} icon={Sparkles} label="Génération" />
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {tab === "vacances" && (
        <Card>
          <div className="mb-3 grid grid-cols-[110px_1fr_1fr_130px_36px] gap-2">
            <Inp value={vForm.code_vacance} onChange={(v) => setVForm({ ...vForm, code_vacance: v })} placeholder="Code" />
            <Inp value={vForm.intitule} onChange={(v) => setVForm({ ...vForm, intitule: v })} placeholder="Intitulé" />
            <Inp value={vForm.departement} onChange={(v) => setVForm({ ...vForm, departement: v })} placeholder="Département" />
            <Inp value={vForm.date_ouverture} type="date" onChange={(v) => setVForm({ ...vForm, date_ouverture: v })} />
            <button onClick={addVac} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {vacs.length === 0 && <p className="text-sm text-muted">Aucune vacance.</p>}
          {vacs.map((v) => (
            <div key={v.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{v.code_vacance}</b> · {v.intitule} <span className="text-muted">· {v.departement || "—"}</span></span>
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">{v.statut}</span>
            </div>
          ))}
        </Card>
      )}

      {tab === "pipeline" && (
        <>
          <Card>
            <h2 className="mb-2 text-sm font-semibold">Nouvelle candidature</h2>
            <div className="grid grid-cols-[1fr_130px_130px_36px] gap-2">
              <Inp value={aForm.nom} onChange={(v) => setAForm({ ...aForm, nom: v })} placeholder="Nom du candidat" />
              <select value={aForm.source} onChange={(e) => setAForm({ ...aForm, source: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 text-sm">
                <option value="spontanee">Spontanée</option><option value="jobboard">Jobboard</option><option value="cooptation">Cooptation</option>
              </select>
              <select value={aForm.code_vacance} onChange={(e) => setAForm({ ...aForm, code_vacance: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 text-sm">
                <option value="">Vacance…</option>
                {vacs.map((v) => <option key={v.id} value={v.code_vacance}>{v.code_vacance}</option>)}
              </select>
              <button onClick={addApp} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
            </div>
          </Card>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
            {ETAPES.map((stage) => {
              const cards = apps.filter((a) => a.etape === stage);
              return (
                <div key={stage} className="rounded-xl bg-black/[0.03] p-2">
                  <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted">{stage} ({cards.length})</div>
                  <div className="flex flex-col gap-2">
                    {cards.map((a) => (
                      <div key={a.id} className="rounded-lg bg-surface p-2 text-sm shadow-sm ring-1 ring-black/5">
                        <div className="font-medium leading-tight">{nameOf.get(a.candidate_id) ?? "—"}</div>
                        <div className="text-xs text-muted">{a.code_vacance}</div>
                        <select value={a.etape} onChange={(e) => move(a.id, e.target.value)} className="mt-1 w-full rounded border border-black/10 bg-white text-xs">
                          {ALL_STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {tab === "kpis" && dash && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi label="Candidatures" value={String(dash.total_candidatures)} />
            <Kpi label="Embauches" value={String(dash.embauches)} />
            <Kpi label="Taux d'embauche" value={dash.taux_embauche_pct + " %"} />
            <Kpi label="Time-to-hire" value={dash.time_to_hire_jours + " j"} />
          </div>
          <Card>
            <h3 className="mb-2 text-sm font-semibold">Entonnoir</h3>
            {ETAPES.map((s) => {
              const n = dash.par_etape[s] ?? 0;
              const max = Math.max(1, ...Object.values(dash.par_etape));
              return (
                <div key={s} className="mb-1.5">
                  <div className="flex justify-between text-xs"><span>{s}</span><span className="text-muted">{n}</span></div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-black/10"><div className="h-full rounded-full bg-primary" style={{ width: `${(n / max) * 100}%` }} /></div>
                </div>
              );
            })}
          </Card>
          {dash.vacances_en_souffrance.length > 0 && (
            <Card>
              <h3 className="mb-2 text-sm font-semibold">Vacances en souffrance</h3>
              {dash.vacances_en_souffrance.map((v) => (
                <div key={v.code_vacance} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
                  <span className="flex items-center gap-2"><Urg level={v.jours_ouverte > 60 ? "high" : "medium"} /> {v.code_vacance}</span>
                  <span className="text-muted">ouverte depuis {v.jours_ouverte} j</span>
                </div>
              ))}
            </Card>
          )}
        </>
      )}

      {tab === "generation" && (
        <>
          <Card className="flex flex-col gap-3">
            <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
              <select value={gType} onChange={(e) => setGType(e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
                {GEN_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
              <Inp value={gEmploi} onChange={setGEmploi} placeholder="Code emploi (RME) — optionnel" />
              <Button onClick={generate} disabled={gLoading}><Sparkles className="h-4 w-4" /> Générer</Button>
            </div>
            <p className="text-xs text-muted">Le prompt est composé depuis le RME/RMC (déterministe) ; la rédaction est faite par l'agent RH (brouillon à valider).</p>
          </Card>
          {gLoading && <Card><Skeleton className="mb-2 h-4 w-1/3" /><Skeleton className="h-4 w-full" /></Card>}
          {gDraft && (
            <Card>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold">{gTitre}</span>
                <Button variant="ghost" onClick={saveDoc}><Save className="h-4 w-4" /> {gSaved ? "Enregistré" : "Enregistrer"}</Button>
              </div>
              <div className="mb-2 rounded-lg bg-amber-100 px-3 py-1 text-xs text-amber-800">Brouillon — à valider avant usage.</div>
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{gDraft}</pre>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof UserPlus; label: string }) {
  return (
    <button onClick={onClick} className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition", active ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <Card><div className="text-xs text-muted">{label}</div><div className="mt-1 text-lg font-semibold">{value}</div></Card>;
}
