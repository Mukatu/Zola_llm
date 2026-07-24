"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import {
  ShieldCheck,
  Gauge,
  ClipboardList,
  ScanSearch,
  FileWarning,
  Trash2,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
} from "lucide-react";
import { Card, Button, Skeleton, Badge, type BadgeTone } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  listObligations,
  createObligation,
  patchObligation,
  deleteObligation,
  listControls,
  createControl,
  patchControl,
  deleteControl,
  listFindings,
  createFinding,
  patchFinding,
  deleteFinding,
  getPlanControle,
  type Obligation,
  type Control,
  type Finding,
  type SyntheseConformite,
} from "@/lib/grc";

type Tab = "synthese" | "obligations" | "controles" | "constats";

const DOMAINES = ["fiscal", "social", "ohada", "donnees", "bailleur", "sectoriel", "autre"];
const PERIODICITES = ["mensuelle", "trimestrielle", "annuelle", "ponctuelle"];
const STATUTS_OBLIGATION = ["active", "suspendue"];
const TYPES_CONTROLE = ["preventif", "detectif"];
const STATUTS_CONTROL = ["planifie", "realise", "suspendu"];
const GRAVITES = ["critique", "majeur", "mineur"];
const STATUTS_FINDING = ["ouvert", "en_cours", "resolu"];

const today = () => new Date().toISOString().slice(0, 10);

export function GrcScreen() {
  const [tab, setTab] = useState<Tab>("synthese");
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader
        icon={ShieldCheck}
        title="Conformité GRC"
        subtitle="Registre de conformité déterministe — obligations, contrôles, constats."
      />
      <div className="flex flex-wrap gap-2">
        <TabBtn active={tab === "synthese"} onClick={() => setTab("synthese")} icon={Gauge} label="Synthèse" />
        <TabBtn active={tab === "obligations"} onClick={() => setTab("obligations")} icon={ClipboardList} label="Obligations" />
        <TabBtn active={tab === "controles"} onClick={() => setTab("controles")} icon={ScanSearch} label="Contrôles" />
        <TabBtn active={tab === "constats"} onClick={() => setTab("constats")} icon={FileWarning} label="Constats" />
      </div>
      {tab === "synthese" && <SyntheseTab />}
      {tab === "obligations" && <ObligationsTab />}
      {tab === "controles" && <ControlesTab />}
      {tab === "constats" && <ConstatsTab />}
    </div>
  );
}

// --- Synthèse ----------------------------------------------------------------

function SyntheseTab() {
  const [s, setS] = useState<SyntheseConformite | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setS(await getPlanControle());
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : "Chargement impossible.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Card><Skeleton className="mb-2 h-6 w-1/3" /><Skeleton className="h-4 w-full" /></Card>;
  if (err) return <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>;
  if (!s) return null;

  const domaineEntries = Object.entries(s.obligations_par_domaine).filter(([, n]) => n > 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Taux de couverture" value={`${s.taux_couverture} %`} />
        <Kpi label="Taux de conformité" value={`${s.taux_conformite} %`} />
        <Kpi label="Contrôles en retard" value={String(s.nb_controls_en_retard)} tone={s.nb_controls_en_retard > 0 ? "red" : undefined} />
        <Kpi label="Obligations sans contrôle" value={String(s.nb_obligations_sans_controle)} tone={s.nb_obligations_sans_controle > 0 ? "amber" : undefined} />
      </div>

      {s.alertes.length > 0 && (
        <Card className="flex flex-col gap-1.5">
          <div className="mb-1 flex items-center gap-2 text-sm font-semibold"><AlertTriangle className="h-4 w-4 text-red-600" /> Alertes ({s.alertes.length})</div>
          {s.alertes.map((a, i) => (
            <div key={i} className="flex items-start gap-2 rounded-lg bg-red-50 p-2.5 text-sm text-red-700">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {a}
            </div>
          ))}
        </Card>
      )}

      <Card>
        <div className="mb-2 text-sm font-semibold">Constats ouverts par gravité</div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Chip label={`Critique ${s.findings_ouverts_par_gravite.critique}`} tone="red" />
          <Chip label={`Majeur ${s.findings_ouverts_par_gravite.majeur}`} tone="amber" />
          <Chip label={`Mineur ${s.findings_ouverts_par_gravite.mineur}`} tone="grey" />
        </div>
      </Card>

      {domaineEntries.length > 0 && (
        <Card>
          <div className="mb-2 text-sm font-semibold">Obligations par domaine</div>
          <div className="flex flex-wrap gap-2 text-xs">
            {domaineEntries.map(([dom, n]) => (
              <Chip key={dom} label={`${dom} ${n}`} tone="grey" />
            ))}
          </div>
        </Card>
      )}

      {s.echeances.length > 0 && (
        <Card className="flex flex-col gap-0 p-0">
          <div className="flex items-center gap-2 border-b border-black/5 p-3 text-sm font-semibold">
            <CalendarClock className="h-4 w-4 text-forest" /> Échéances à venir
          </div>
          <div className="divide-y divide-black/5">
            {s.echeances.map((e, i) => (
              <div key={i} className="flex items-center justify-between px-3 py-2 text-sm">
                <div>
                  <span className="font-medium">{e.libelle}</span>
                  <span className="ml-2 rounded-full bg-black/5 px-1.5 py-0.5 text-[10px] uppercase text-muted">{e.type}</span>
                  <div className="text-xs text-muted">{e.reference}</div>
                </div>
                <div className="text-right">
                  <div className="tabular-nums">{e.date_limite}</div>
                  <div className={clsx("text-xs font-medium", e.jours_restants < 0 ? "text-red-600" : "text-muted")}>
                    {e.jours_restants < 0 ? `en retard de ${Math.abs(e.jours_restants)} j` : `dans ${e.jours_restants} j`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: "red" | "amber" }) {
  return (
    <Card className="py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={clsx("text-lg font-bold tabular-nums", tone === "red" ? "text-red-600" : tone === "amber" ? "text-amber-700" : "text-ink")}>{value}</div>
    </Card>
  );
}

function Chip({ label, tone }: { label: string; tone: "forest" | "amber" | "red" | "grey" }) {
  const c =
    tone === "forest" ? "bg-mint/25 text-forest"
    : tone === "amber" ? "bg-amber-100 text-amber-800"
    : tone === "red" ? "bg-red-100 text-red-700"
    : "bg-black/5 text-ink/70";
  return <span className={clsx("rounded-full px-2.5 py-1 font-medium", c)}>{label}</span>;
}

// --- Obligations ---------------------------------------------------------------

function ObligationsTab() {
  const [list, setList] = useState<Obligation[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [intitule, setIntitule] = useState("");
  const [reference, setReference] = useState("");
  const [domaine, setDomaine] = useState("fiscal");
  const [periodicite, setPeriodicite] = useState("mensuelle");
  const [autorite, setAutorite] = useState("");
  const [echeance, setEcheance] = useState("");
  const [statut, setStatut] = useState("active");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      setList(await listObligations());
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  async function create() {
    if (!intitule.trim()) {
      setErr("L'intitulé est requis.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await createObligation({
        intitule: intitule.trim(),
        reference: reference.trim() || undefined,
        domaine,
        periodicite,
        autorite: autorite.trim() || undefined,
        echeance: echeance || null,
        statut,
      });
      setIntitule("");
      setReference("");
      setAutorite("");
      setEcheance("");
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Création impossible.");
    } finally {
      setSaving(false);
    }
  }

  const toggleStatut = async (o: Obligation) => {
    setErr(null);
    try {
      await patchObligation(o.id, { statut: o.statut === "active" ? "suspendue" : "active" });
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Action impossible.");
    }
  };

  const remove = async (id: string) => {
    setErr(null);
    try {
      await deleteObligation(id);
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Suppression impossible.");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Card className="grid gap-3 sm:grid-cols-2">
        <div className="col-span-full"><Field label="Intitulé *"><Inp className="w-full" value={intitule} onChange={setIntitule} placeholder="ex : Déclaration TVA mensuelle" /></Field></div>
        <Field label="Référence"><Inp className="w-full" value={reference} onChange={setReference} placeholder="ex : OBL-2026-001" /></Field>
        <Field label="Autorité"><Inp className="w-full" value={autorite} onChange={setAutorite} placeholder="ex : DGI" /></Field>
        <Field label="Domaine">
          <select value={domaine} onChange={(e) => setDomaine(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {DOMAINES.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
        <Field label="Périodicité">
          <select value={periodicite} onChange={(e) => setPeriodicite(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {PERIODICITES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Échéance"><Inp className="w-full" value={echeance} onChange={setEcheance} type="date" /></Field>
        <Field label="Statut">
          <select value={statut} onChange={(e) => setStatut(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {STATUTS_OBLIGATION.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <div className="col-span-full flex justify-end"><Button onClick={create} disabled={saving}>Ajouter l&apos;obligation</Button></div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {loading && <Card><Skeleton className="h-5 w-1/2" /></Card>}

      <Card className="flex flex-col gap-2">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold"><ClipboardList className="h-4 w-4 text-forest" /> Obligations ({list.length})</div>
        {!loading && list.length === 0 && <p className="text-sm text-muted">Aucune obligation enregistrée.</p>}
        {list.map((o) => (
          <div key={o.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
            <div className="min-w-40">
              <div className="font-medium">{o.intitule}</div>
              <div className="text-xs text-muted">{o.reference || "—"} · {o.autorite || "—"}</div>
            </div>
            <DomaineBadge domaine={o.domaine} />
            <span className="text-xs text-muted">Échéance : {o.echeance ?? "—"}</span>
            <StatutObligationBadge statut={o.statut} />
            <div className="ml-auto flex items-center gap-1.5">
              <MiniBtn onClick={() => toggleStatut(o)} tone="forest">{o.statut === "active" ? "Suspendre" : "Réactiver"}</MiniBtn>
              <button onClick={() => remove(o.id)} className="grid h-7 w-7 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

// --- Contrôles -----------------------------------------------------------------

function ControlesTab() {
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [list, setList] = useState<Control[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [intitule, setIntitule] = useState("");
  const [typeControle, setTypeControle] = useState("preventif");
  const [frequence, setFrequence] = useState("");
  const [responsable, setResponsable] = useState("");
  const [prochaineExecution, setProchaineExecution] = useState("");
  const [obligationId, setObligationId] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [obs, ctrls] = await Promise.all([listObligations(), listControls()]);
      setObligations(obs);
      setList(ctrls);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  async function create() {
    if (!intitule.trim()) {
      setErr("L'intitulé est requis.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await createControl({
        intitule: intitule.trim(),
        type_controle: typeControle,
        frequence: frequence.trim() || undefined,
        responsable: responsable.trim() || undefined,
        prochaine_execution: prochaineExecution || null,
        obligation_id: obligationId || null,
      });
      setIntitule("");
      setFrequence("");
      setResponsable("");
      setProchaineExecution("");
      setObligationId("");
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Création impossible.");
    } finally {
      setSaving(false);
    }
  }

  const marquerRealise = async (c: Control) => {
    setErr(null);
    try {
      await patchControl(c.id, { statut: "realise", derniere_execution: today() });
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Action impossible.");
    }
  };

  const remove = async (id: string) => {
    setErr(null);
    try {
      await deleteControl(id);
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Suppression impossible.");
    }
  };

  const obligationLabel = (id: string | null) => obligations.find((o) => o.id === id)?.intitule ?? null;

  return (
    <div className="flex flex-col gap-4">
      <Card className="grid gap-3 sm:grid-cols-2">
        <div className="col-span-full"><Field label="Intitulé *"><Inp className="w-full" value={intitule} onChange={setIntitule} placeholder="ex : Vérification des retenues à la source" /></Field></div>
        <Field label="Type de contrôle">
          <select value={typeControle} onChange={(e) => setTypeControle(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {TYPES_CONTROLE.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Fréquence"><Inp className="w-full" value={frequence} onChange={setFrequence} placeholder="ex : mensuelle" /></Field>
        <Field label="Responsable"><Inp className="w-full" value={responsable} onChange={setResponsable} placeholder="ex : Contrôle interne" /></Field>
        <Field label="Prochaine exécution"><Inp className="w-full" value={prochaineExecution} onChange={setProchaineExecution} type="date" /></Field>
        <Field label="Obligation liée">
          <select value={obligationId} onChange={(e) => setObligationId(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            <option value="">— aucune —</option>
            {obligations.map((o) => <option key={o.id} value={o.id}>{o.intitule}</option>)}
          </select>
        </Field>
        <div className="col-span-full flex justify-end"><Button onClick={create} disabled={saving}>Ajouter le contrôle</Button></div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {loading && <Card><Skeleton className="h-5 w-1/2" /></Card>}

      <Card className="flex flex-col gap-2">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold"><ScanSearch className="h-4 w-4 text-forest" /> Contrôles ({list.length})</div>
        {!loading && list.length === 0 && <p className="text-sm text-muted">Aucun contrôle enregistré.</p>}
        {list.map((c) => {
          const overdue = !!c.prochaine_execution && c.prochaine_execution < today() && c.statut !== "realise";
          return (
            <div key={c.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
              <div className="min-w-40">
                <div className="font-medium">{c.intitule}</div>
                <div className="text-xs text-muted">{c.responsable || "—"}{obligationLabel(c.obligation_id) ? ` · ${obligationLabel(c.obligation_id)}` : ""}</div>
              </div>
              <TypeControleBadge type={c.type_controle} />
              <span className={clsx("text-xs", overdue ? "font-medium text-red-600" : "text-muted")}>
                Prochaine exéc. : {c.prochaine_execution ?? "—"}{overdue ? " (en retard)" : ""}
              </span>
              <StatutControlBadge statut={c.statut} />
              <div className="ml-auto flex items-center gap-1.5">
                {c.statut !== "realise" && <MiniBtn onClick={() => marquerRealise(c)} tone="forest">Marquer réalisé</MiniBtn>}
                <button onClick={() => remove(c.id)} className="grid h-7 w-7 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>
          );
        })}
      </Card>
    </div>
  );
}

// --- Constats --------------------------------------------------------------

function ConstatsTab() {
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [list, setList] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [intitule, setIntitule] = useState("");
  const [gravite, setGravite] = useState("mineur");
  const [dateConstat, setDateConstat] = useState(today());
  const [obligationId, setObligationId] = useState("");
  const [planAction, setPlanAction] = useState("");
  const [responsable, setResponsable] = useState("");
  const [echeanceCorrection, setEcheanceCorrection] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [obs, findings] = await Promise.all([listObligations(), listFindings()]);
      setObligations(obs);
      setList(findings);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  async function create() {
    if (!intitule.trim()) {
      setErr("L'intitulé est requis.");
      return;
    }
    if (!dateConstat) {
      setErr("La date de constat est requise.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await createFinding({
        intitule: intitule.trim(),
        gravite,
        date_constat: dateConstat,
        obligation_id: obligationId || null,
        plan_action: planAction.trim() || undefined,
        responsable: responsable.trim() || undefined,
        echeance_correction: echeanceCorrection || null,
      });
      setIntitule("");
      setPlanAction("");
      setResponsable("");
      setEcheanceCorrection("");
      setObligationId("");
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Création impossible.");
    } finally {
      setSaving(false);
    }
  }

  const avancer = async (f: Finding) => {
    const suivant: Record<string, string> = { ouvert: "en_cours", en_cours: "resolu" };
    const next = suivant[f.statut];
    if (!next) return;
    setErr(null);
    try {
      await patchFinding(f.id, { statut: next });
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Action impossible.");
    }
  };

  const remove = async (id: string) => {
    setErr(null);
    try {
      await deleteFinding(id);
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Suppression impossible.");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Card className="grid gap-3 sm:grid-cols-2">
        <div className="col-span-full"><Field label="Intitulé *"><Inp className="w-full" value={intitule} onChange={setIntitule} placeholder="ex : Retard de déclaration TVA" /></Field></div>
        <Field label="Gravité">
          <select value={gravite} onChange={(e) => setGravite(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {GRAVITES.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </Field>
        <Field label="Date du constat *"><Inp className="w-full" value={dateConstat} onChange={setDateConstat} type="date" /></Field>
        <Field label="Obligation liée">
          <select value={obligationId} onChange={(e) => setObligationId(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            <option value="">— aucune —</option>
            {obligations.map((o) => <option key={o.id} value={o.id}>{o.intitule}</option>)}
          </select>
        </Field>
        <Field label="Échéance de correction"><Inp className="w-full" value={echeanceCorrection} onChange={setEcheanceCorrection} type="date" /></Field>
        <Field label="Responsable"><Inp className="w-full" value={responsable} onChange={setResponsable} placeholder="ex : Direction financière" /></Field>
        <div className="col-span-full"><Field label="Plan d'action"><Inp className="w-full" value={planAction} onChange={setPlanAction} placeholder="ex : Régularisation et mise en place d'un rappel automatique" /></Field></div>
        <div className="col-span-full flex justify-end"><Button onClick={create} disabled={saving}>Ajouter le constat</Button></div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {loading && <Card><Skeleton className="h-5 w-1/2" /></Card>}

      <Card className="flex flex-col gap-2">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold"><FileWarning className="h-4 w-4 text-forest" /> Constats ({list.length})</div>
        {!loading && list.length === 0 && <p className="text-sm text-muted">Aucun constat enregistré.</p>}
        {list.map((f) => (
          <div key={f.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
            <div className="min-w-40">
              <div className="font-medium">{f.intitule}</div>
              <div className="text-xs text-muted">Constaté le {f.date_constat}{f.echeance_correction ? ` · correction avant ${f.echeance_correction}` : ""}</div>
            </div>
            <GraviteBadge gravite={f.gravite} />
            <StatutFindingBadge statut={f.statut} />
            <div className="ml-auto flex items-center gap-1.5">
              {f.statut !== "resolu" && (
                <MiniBtn onClick={() => avancer(f)} tone="forest">
                  {f.statut === "ouvert" ? "Passer en cours" : "Marquer résolu"}
                </MiniBtn>
              )}
              <button onClick={() => remove(f.id)} className="grid h-7 w-7 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

// --- primitives --------------------------------------------------------------

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof Gauge; label: string }) {
  return (
    <button onClick={onClick} className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition", active ? "bg-forest text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-sm"><span className="mb-1 block font-medium">{label}</span>{children}</label>;
}

function MiniBtn({ onClick, tone, children }: { onClick: () => void; tone: "forest" | "red"; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={clsx("rounded-lg px-2.5 py-1 text-xs font-medium transition", tone === "forest" ? "bg-forest/10 text-forest hover:bg-forest/20" : "bg-red-50 text-red-600 hover:bg-red-100")}>
      {children}
    </button>
  );
}

function DomaineBadge({ domaine }: { domaine: string }) {
  return <Badge tone="grey" className="!px-2.5 !bg-black/5 !text-ink/70">{domaine}</Badge>;
}

const STATUT_OBLIGATION_TONE: Record<string, BadgeTone> = { active: "green", suspendue: "grey" };
const STATUT_OBLIGATION_LABEL: Record<string, string> = { active: "Active", suspendue: "Suspendue" };

function StatutObligationBadge({ statut }: { statut: string }) {
  const tone = STATUT_OBLIGATION_TONE[statut] ?? "grey";
  return (
    <Badge
      tone={tone}
      className={clsx(
        "!px-2.5",
        statut === "active" && "!bg-forest !text-white",
        statut === "suspendue" && "!bg-black/5 !text-ink/60",
        !STATUT_OBLIGATION_TONE[statut] && "!bg-black/5 !text-ink/70",
      )}
    >
      {STATUT_OBLIGATION_LABEL[statut] ?? statut}
    </Badge>
  );
}

const TYPE_CONTROLE_TONE: Record<string, BadgeTone> = { preventif: "mint", detectif: "grey" };
const TYPE_CONTROLE_LABEL: Record<string, string> = { preventif: "Préventif", detectif: "Détectif" };

function TypeControleBadge({ type }: { type: string }) {
  const tone = TYPE_CONTROLE_TONE[type] ?? "grey";
  return (
    <Badge tone={tone} className={clsx("!px-2.5", tone === "grey" && "!bg-black/5 !text-ink/70")}>
      {TYPE_CONTROLE_LABEL[type] ?? type}
    </Badge>
  );
}

const STATUT_CONTROL_TONE: Record<string, BadgeTone> = { planifie: "amber", realise: "green", suspendu: "grey" };
const STATUT_CONTROL_LABEL: Record<string, string> = { planifie: "Planifié", realise: "Réalisé", suspendu: "Suspendu" };

function StatutControlBadge({ statut }: { statut: string }) {
  const tone = STATUT_CONTROL_TONE[statut] ?? "grey";
  return (
    <Badge
      tone={tone}
      className={clsx(
        "!px-2.5",
        statut === "realise" && "!bg-forest !text-white",
        statut === "suspendu" && "!bg-black/5 !text-ink/60",
        !STATUT_CONTROL_TONE[statut] && "!bg-black/5 !text-ink/70",
      )}
    >
      {STATUT_CONTROL_LABEL[statut] ?? statut}
    </Badge>
  );
}

const GRAVITE_TONE: Record<string, BadgeTone> = { critique: "red", majeur: "amber", mineur: "grey" };
const GRAVITE_LABEL: Record<string, string> = { critique: "Critique", majeur: "Majeur", mineur: "Mineur" };

function GraviteBadge({ gravite }: { gravite: string }) {
  const tone = GRAVITE_TONE[gravite] ?? "grey";
  return (
    <Badge
      tone={tone}
      className={clsx(
        "!px-2.5",
        gravite === "mineur" && "!bg-black/5 !text-ink/60",
        !GRAVITE_TONE[gravite] && "!bg-black/5 !text-ink/70",
      )}
    >
      {GRAVITE_LABEL[gravite] ?? gravite}
    </Badge>
  );
}

const STATUT_FINDING_TONE: Record<string, BadgeTone> = { ouvert: "red", en_cours: "amber", resolu: "green" };
const STATUT_FINDING_LABEL: Record<string, string> = { ouvert: "Ouvert", en_cours: "En cours", resolu: "Résolu" };

function StatutFindingBadge({ statut }: { statut: string }) {
  const tone = STATUT_FINDING_TONE[statut] ?? "grey";
  return (
    <Badge
      tone={tone}
      className={clsx(
        "!px-2.5",
        statut === "resolu" && "!bg-forest !text-white",
        !STATUT_FINDING_TONE[statut] && "!bg-black/5 !text-ink/70",
      )}
    >
      {STATUT_FINDING_LABEL[statut] ?? statut}
    </Badge>
  );
}
