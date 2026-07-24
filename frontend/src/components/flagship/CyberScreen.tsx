"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import {
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Save,
  Trash2,
  Info,
  Radar,
  Plus,
  AlertTriangle,
  Settings,
} from "lucide-react";
import { Card, Button, Skeleton, SeverityBadge } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  getBaseline,
  cyberAudit,
  createCyberAudit,
  listCyberAudits,
  deleteCyberAudit,
  EMPTY_CONFIG_AUDIT,
  cyberAnomalies,
  createCyberDetection,
  listCyberDetections,
  decideCyberDetection,
  deleteCyberDetection,
  getCyberParams,
  editCyberParams,
  validateCyberParams,
  TYPE_EVENEMENT_LABELS,
  type Controle,
  type ConfigAudit,
  type ControleKey,
  type AuditResult,
  type CyberAudit,
  type Fonction,
  type Severite,
  type LogEvent,
  type TypeEvenement,
  type AnalyseAnomalies,
  type CyberDetection,
  type CyberSeuils,
  type CyberParamsView,
} from "@/lib/cyber";

// Traduit les codes d'erreur backend (detail JSON `{"detail": "..."}`) en messages FR.
function messageFromCyberError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  let detail = e.detail;
  try {
    const parsed = JSON.parse(e.detail) as { detail?: string };
    if (parsed?.detail) detail = parsed.detail;
  } catch {
    /* detail n'est pas du JSON — on garde le texte brut */
  }
  if (detail.includes("aucun_parametre_tenant_a_valider")) return "Éditez d'abord un paramètre avant de le valider.";
  return fallback;
}

const FONCTION_LABELS: Record<Fonction, string> = {
  identify: "Identifier",
  protect: "Protéger",
  detect: "Détecter",
  respond: "Répondre",
  recover: "Rétablir",
};

const FONCTION_ORDER: Fonction[] = ["identify", "protect", "detect", "respond", "recover"];

type Tab = "durcissement" | "detection" | "parametres";

export function CyberScreen() {
  const [tab, setTab] = useState<Tab>("durcissement");
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader
        icon={ShieldCheck}
        title="Cyber-défense"
        subtitle="Durcissement de configuration et détection d'anomalies — défensif, déterministe, sans action offensive."
      />
      <div className="flex flex-wrap gap-2">
        <TabBtn active={tab === "durcissement"} onClick={() => setTab("durcissement")} icon={ShieldCheck} label="Durcissement" />
        <TabBtn active={tab === "detection"} onClick={() => setTab("detection")} icon={Radar} label="Détection d'anomalies" />
        <TabBtn active={tab === "parametres"} onClick={() => setTab("parametres")} icon={Settings} label="Paramètres" />
      </div>
      {tab === "durcissement" && <DurcissementTab />}
      {tab === "detection" && <DetectionTab />}
      {tab === "parametres" && <ParametresTab />}
    </div>
  );
}

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof ShieldCheck; label: string }) {
  return (
    <button onClick={onClick} className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition", active ? "bg-forest text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function DurcissementTab() {
  const [controles, setControles] = useState<Controle[]>([]);
  const [referenceCadre, setReferenceCadre] = useState("");
  const [config, setConfig] = useState<ConfigAudit>(EMPTY_CONFIG_AUDIT);
  const [loadingBaseline, setLoadingBaseline] = useState(true);
  const [baselineErr, setBaselineErr] = useState<string | null>(null);

  const [res, setRes] = useState<AuditResult | null>(null);
  const [analysing, setAnalysing] = useState(false);
  const [analyseErr, setAnalyseErr] = useState<string | null>(null);

  const [cible, setCible] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  const [audits, setAudits] = useState<CyberAudit[]>([]);
  const [auditsLoading, setAuditsLoading] = useState(true);
  const [auditsErr, setAuditsErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoadingBaseline(true);
      try {
        const b = await getBaseline();
        setControles(b.controles);
        setReferenceCadre(b.reference_cadre);
      } catch (e) {
        setBaselineErr(e instanceof ApiError ? e.message : "Chargement de la base de contrôles impossible.");
      } finally {
        setLoadingBaseline(false);
      }
    })();
  }, []);

  const refreshAudits = useCallback(async () => {
    setAuditsLoading(true);
    try {
      const r = await listCyberAudits();
      setAudits(r.audits);
    } catch (e) {
      setAuditsErr(e instanceof ApiError ? e.message : "Chargement du registre impossible.");
    } finally {
      setAuditsLoading(false);
    }
  }, []);
  useEffect(() => {
    refreshAudits();
  }, [refreshAudits]);

  const setValue = (cle: string, v: boolean | null) => setConfig((s) => ({ ...s, [cle as ControleKey]: v }));

  async function analyser() {
    setAnalysing(true);
    setAnalyseErr(null);
    setRes(null);
    setSaved(null);
    try {
      setRes(await cyberAudit(config));
    } catch (e) {
      setAnalyseErr(e instanceof ApiError ? e.message : "Service indisponible.");
    } finally {
      setAnalysing(false);
    }
  }

  async function enregistrer() {
    setSaving(true);
    setAnalyseErr(null);
    try {
      const rec = await createCyberAudit({ cible: cible.trim() || "Cible non nommée", config });
      setSaved(rec.id);
      await refreshAudits();
    } catch (e) {
      setAnalyseErr(e instanceof ApiError ? e.message : "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  }

  const supprimer = async (id: string) => {
    setAuditsErr(null);
    try {
      await deleteCyberAudit(id);
      await refreshAudits();
    } catch (e) {
      setAuditsErr(e instanceof ApiError ? e.message : "Suppression impossible.");
    }
  };

  const grouped = FONCTION_ORDER.map((f) => ({ fonction: f, items: controles.filter((c) => c.fonction === f) })).filter(
    (g) => g.items.length > 0,
  );

  return (
    <>
      {loadingBaseline && <Card><Skeleton className="mb-2 h-5 w-1/3" /><Skeleton className="h-4 w-full" /></Card>}
      {baselineErr && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{baselineErr}</p></Card>}

      {!loadingBaseline && !baselineErr && (
        <Card className="flex flex-col gap-4">
          {grouped.map((g) => (
            <div key={g.fonction} className="flex flex-col gap-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted">{FONCTION_LABELS[g.fonction]}</div>
              <div className="flex flex-col gap-1.5">
                {g.items.map((c) => (
                  <div key={c.cle} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
                    <SeverityBadge level={c.severite} />
                    <span className="min-w-0 flex-1 font-medium">{c.libelle}</span>
                    <TriState value={config[c.cle as ControleKey] ?? null} onChange={(v) => setValue(c.cle, v)} />
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div className="flex justify-end border-t border-black/5 pt-3">
            <Button onClick={analyser} disabled={analysing}>Analyser</Button>
          </div>
        </Card>
      )}

      {analysing && <Card><Skeleton className="mb-2 h-6 w-1/3" /><Skeleton className="h-4 w-full" /></Card>}
      {analyseErr && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{analyseErr}</p></Card>}

      {res && (
        <Card className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <ScoreDial score={Number(res.score_conformite)} />
            <div className="flex flex-col gap-1">
              <NiveauBadge niveau={res.niveau} />
              <div className="text-xs text-muted">
                {res.nb_conforme} conforme(s) · {res.nb_non_conforme} non conforme(s) · {res.nb_a_verifier} à vérifier
              </div>
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Synthèse par fonction (NIST CSF)</div>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(res.par_fonction).map(([f, s]) => (
                <div key={f} className="flex items-center justify-between rounded-lg bg-black/[0.02] px-3 py-2 text-sm">
                  <span className="font-medium">{FONCTION_LABELS[f as Fonction] ?? f}</span>
                  <span className="text-xs text-muted">
                    <span className="text-forest">{s.conforme} ok</span> · <span className="text-red-600">{s.non_conforme} non conf.</span> · <span>{s.a_verifier} à vérifier</span>
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Constats (non-conformités en priorité)</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted">
                  <tr className="text-left">
                    <th className="py-1 pr-3">Statut</th>
                    <th className="pr-3">Sévérité</th>
                    <th className="pr-3">Contrôle</th>
                    <th className="pr-3">Remédiation</th>
                  </tr>
                </thead>
                <tbody>
                  {res.findings.map((f) => (
                    <tr key={f.cle} className="border-t border-black/5 align-top">
                      <td className="py-1.5 pr-3"><StatutBadge statut={f.statut} /></td>
                      <td className="pr-3"><SeverityBadge level={f.severite} /></td>
                      <td className="pr-3 font-medium">{f.libelle}</td>
                      <td className="pr-3 text-ink/70">{f.remediation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <p className="flex items-start gap-1.5 text-xs text-muted"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {res.reference_cadre}</p>

          <div className="flex flex-wrap items-center gap-3 border-t border-black/5 pt-3">
            <Inp className="w-56" value={cible} onChange={setCible} placeholder="Cible (ex : Serveur applicatif prod)" />
            <Button onClick={enregistrer} disabled={saving}><Save className="h-4 w-4" /> Enregistrer l&apos;audit</Button>
            {saved && <span className="flex items-center gap-1.5 text-sm font-medium text-forest"><CheckCircle2 className="h-4 w-4" /> Enregistré</span>}
          </div>
        </Card>
      )}

      <Card className="flex flex-col gap-2">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold"><ShieldAlert className="h-4 w-4 text-forest" /> Registre des audits ({audits.length})</div>
        {auditsErr && <p className="text-sm text-amber-700">{auditsErr}</p>}
        {auditsLoading && <Skeleton className="h-5 w-1/2" />}
        {!auditsLoading && audits.length === 0 && <p className="text-sm text-muted">Aucun audit enregistré.</p>}
        {audits.map((a) => (
          <div key={a.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
            <div className="min-w-40">
              <div className="font-medium">{a.cible}</div>
              <div className="text-xs text-muted">{a.created_at ? new Date(a.created_at).toLocaleDateString("fr-FR") : "—"}</div>
            </div>
            <span className="rounded-full bg-black/5 px-2.5 py-0.5 text-xs font-semibold">{a.score_conformite} %</span>
            <NiveauBadge niveau={a.niveau} />
            <span className="text-xs text-muted">{a.nb_non_conforme} non conforme(s)</span>
            <button onClick={() => supprimer(a.id)} className="ml-auto grid h-7 w-7 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
          </div>
        ))}
      </Card>
    </>
  );
}

// --- Détection d'anomalies ---------------------------------------------------

const NEW_LOG_EVENT: LogEvent = { horodatage: "", type: "auth_failure", utilisateur: "", source_ip: "" };
const TYPE_EVENEMENT_OPTIONS = Object.keys(TYPE_EVENEMENT_LABELS) as TypeEvenement[];

function DetectionTab() {
  const [events, setEvents] = useState<LogEvent[]>([
    { horodatage: "2026-07-24T08:00", type: "auth_success", utilisateur: "jmabiala", source_ip: "10.0.0.14" },
    { horodatage: "2026-07-24T02:15", type: "auth_failure", utilisateur: "admin", source_ip: "41.exemple.203.9" },
  ]);
  const [res, setRes] = useState<AnalyseAnomalies | null>(null);
  const [analysing, setAnalysing] = useState(false);
  const [analyseErr, setAnalyseErr] = useState<string | null>(null);

  const [cible, setCible] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  const [detections, setDetections] = useState<CyberDetection[]>([]);
  const [detLoading, setDetLoading] = useState(true);
  const [detErr, setDetErr] = useState<string | null>(null);

  const refreshDetections = useCallback(async () => {
    setDetLoading(true);
    try {
      const r = await listCyberDetections();
      setDetections(r.detections);
    } catch (e) {
      setDetErr(e instanceof ApiError ? e.message : "Chargement du registre impossible.");
    } finally {
      setDetLoading(false);
    }
  }, []);
  useEffect(() => {
    refreshDetections();
  }, [refreshDetections]);

  const updEvent = (i: number, k: keyof LogEvent, v: string) =>
    setEvents((s) => s.map((e, j) => (j === i ? { ...e, [k]: v } : e)));
  const removeEvent = (i: number) => setEvents((s) => s.filter((_, j) => j !== i));
  const addEvent = () => setEvents((s) => [...s, { ...NEW_LOG_EVENT }]);

  const validEvents = () => events.filter((e) => e.horodatage.trim() !== "");

  async function analyser() {
    setAnalysing(true);
    setAnalyseErr(null);
    setRes(null);
    setSaved(null);
    try {
      setRes(await cyberAnomalies({ events: validEvents() }));
    } catch (e) {
      setAnalyseErr(e instanceof ApiError ? e.message : "Service indisponible.");
    } finally {
      setAnalysing(false);
    }
  }

  async function enregistrer() {
    setSaving(true);
    setAnalyseErr(null);
    try {
      const rec = await createCyberDetection({ cible: cible.trim() || "Cible non nommée", events: validEvents() });
      setSaved(rec.id);
      await refreshDetections();
    } catch (e) {
      setAnalyseErr(e instanceof ApiError ? e.message : "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  }

  const decider = async (id: string, statut: "classee" | "traitee") => {
    setDetErr(null);
    try {
      await decideCyberDetection(id, { statut });
      await refreshDetections();
    } catch (e) {
      setDetErr(e instanceof ApiError ? e.message : "Action impossible.");
    }
  };

  const supprimer = async (id: string) => {
    setDetErr(null);
    try {
      await deleteCyberDetection(id);
      await refreshDetections();
    } catch (e) {
      setDetErr(e instanceof ApiError ? e.message : "Suppression impossible.");
    }
  };

  return (
    <>
      <Card className="flex flex-col gap-2">
        <div className="mb-1 text-sm font-semibold">Journal d&apos;événements à analyser</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted">
              <tr className="text-left">
                <th className="py-1 pr-3">Horodatage</th>
                <th className="pr-3">Type</th>
                <th className="pr-3">Utilisateur</th>
                <th className="pr-3">IP source</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={i} className="border-t border-black/5">
                  <td className="py-1.5 pr-3"><Inp className="w-44" value={e.horodatage} onChange={(v) => updEvent(i, "horodatage", v)} type="datetime-local" /></td>
                  <td className="pr-3">
                    <select value={e.type} onChange={(ev) => updEvent(i, "type", ev.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1.5 text-sm">
                      {TYPE_EVENEMENT_OPTIONS.map((t) => (
                        <option key={t} value={t}>{TYPE_EVENEMENT_LABELS[t]}</option>
                      ))}
                    </select>
                  </td>
                  <td className="pr-3"><Inp className="w-32" value={e.utilisateur ?? ""} onChange={(v) => updEvent(i, "utilisateur", v)} placeholder="ex : jmabiala" /></td>
                  <td className="pr-3"><Inp className="w-36" value={e.source_ip ?? ""} onChange={(v) => updEvent(i, "source_ip", v)} placeholder="ex : 10.0.0.14" /></td>
                  <td>
                    <button onClick={() => removeEvent(i)} className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-black/5 pt-3">
          <button onClick={addEvent} className="flex items-center gap-1.5 text-sm text-forest hover:underline"><Plus className="h-4 w-4" /> Ajouter un événement</button>
          <Button onClick={analyser} disabled={analysing || validEvents().length === 0}>Analyser</Button>
        </div>
      </Card>

      {analysing && <Card><Skeleton className="mb-2 h-6 w-1/3" /><Skeleton className="h-4 w-full" /></Card>}
      {analyseErr && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{analyseErr}</p></Card>}

      {res && (
        <Card className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <DetectionNiveauBadge niveau={res.niveau} />
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
              <Stat label="Événements" value={String(res.nb_events)} />
              <Stat label="Échecs d'authentification" value={String(res.nb_echecs_auth)} />
              <Stat label="IP distinctes" value={String(res.nb_ip_distinctes)} />
              <Stat label="Utilisateurs" value={String(res.nb_utilisateurs)} />
            </div>
          </div>

          {res.anomalies.length === 0 ? (
            <p className="flex items-center gap-1.5 text-sm text-forest"><CheckCircle2 className="h-4 w-4" /> Aucune anomalie détectée sur ce journal.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {res.anomalies.map((a, i) => (
                <div key={i} className={clsx("flex items-start gap-2 rounded-lg p-3 text-sm",
                  a.niveau === "alerte" ? "bg-red-50 text-red-700" : a.niveau === "attention" ? "bg-amber-50 text-amber-800" : "bg-mint/15 text-forest")}>
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <div className="font-semibold">{a.titre} <span className="font-normal opacity-70">— {a.entite}</span></div>
                    <div className="opacity-90">{a.detail}</div>
                    <div className="text-xs opacity-70">{a.occurrences} occurrence(s)</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <p className="flex items-start gap-1.5 text-xs text-muted"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {res.reference_cadre}</p>

          <div className="flex flex-wrap items-center gap-3 border-t border-black/5 pt-3">
            <Inp className="w-56" value={cible} onChange={setCible} placeholder="Cible (ex : Serveur applicatif prod)" />
            <Button onClick={enregistrer} disabled={saving}><Save className="h-4 w-4" /> Enregistrer la détection</Button>
            {saved && <span className="flex items-center gap-1.5 text-sm font-medium text-forest"><CheckCircle2 className="h-4 w-4" /> Enregistré</span>}
          </div>
        </Card>
      )}

      <Card className="flex flex-col gap-2">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold"><Radar className="h-4 w-4 text-forest" /> Registre des détections ({detections.length})</div>
        {detErr && <p className="text-sm text-amber-700">{detErr}</p>}
        {detLoading && <Skeleton className="h-5 w-1/2" />}
        {!detLoading && detections.length === 0 && <p className="text-sm text-muted">Aucune détection enregistrée.</p>}
        {detections.map((d) => (
          <div key={d.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
            <div className="min-w-40">
              <div className="font-medium">{d.cible}</div>
              <div className="text-xs text-muted">{d.created_at ? new Date(d.created_at).toLocaleDateString("fr-FR") : "—"}</div>
            </div>
            <DetectionNiveauBadge niveau={d.niveau} />
            <span className="text-xs text-muted">{d.nb_anomalies} anomalie(s) · {d.nb_events} événement(s)</span>
            <DetectionStatutBadge statut={d.statut} />
            <div className="ml-auto flex flex-wrap items-center gap-1.5">
              {d.statut === "a_examiner" && (
                <>
                  <MiniBtn onClick={() => decider(d.id, "classee")} tone="forest">Classer sans suite</MiniBtn>
                  <MiniBtn onClick={() => decider(d.id, "traitee")} tone="red">Traité</MiniBtn>
                </>
              )}
              <button onClick={() => supprimer(d.id)} className="grid h-7 w-7 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ))}
      </Card>
    </>
  );
}

// --- Paramètres gouvernés (seuils + base de durcissement) --------------------

const SEUIL_FIELDS: { key: keyof CyberSeuils; label: string }[] = [
  { key: "fenetre_minutes", label: "Fenêtre (minutes)" },
  { key: "seuil_echecs", label: "Seuil d'échecs" },
  { key: "heure_ouverture", label: "Heure d'ouverture" },
  { key: "heure_fermeture", label: "Heure de fermeture" },
  { key: "seuil_ips_par_user", label: "Seuil IP / utilisateur" },
];

const SEVERITE_OPTIONS: Severite[] = ["critical", "high", "medium", "low"];

type ControleDraft = { severite: Severite; active: boolean };

function ParametresTab() {
  const [view, setView] = useState<CyberParamsView | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [validatedBy, setValidatedBy] = useState("");

  const [seuilsDraft, setSeuilsDraft] = useState<Record<string, string>>({});
  const [controlesDraft, setControlesDraft] = useState<Record<string, ControleDraft>>({});

  const applyView = useCallback((v: CyberParamsView) => {
    setView(v);
    setSeuilsDraft({
      fenetre_minutes: String(v.seuils.fenetre_minutes),
      seuil_echecs: String(v.seuils.seuil_echecs),
      heure_ouverture: String(v.seuils.heure_ouverture),
      heure_fermeture: String(v.seuils.heure_fermeture),
      seuil_ips_par_user: String(v.seuils.seuil_ips_par_user),
    });
    setControlesDraft(Object.fromEntries(v.controles.map((c) => [c.cle, { severite: c.severite, active: c.active }])));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      applyView(await getCyberParams());
      setErr(null);
    } catch (e) {
      setErr(messageFromCyberError(e, "Chargement des paramètres impossible."));
    } finally {
      setLoading(false);
    }
  }, [applyView]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function saveSeuils() {
    setBusy(true);
    setErr(null);
    try {
      const seuils: Partial<CyberSeuils> = {
        fenetre_minutes: Number(seuilsDraft.fenetre_minutes),
        seuil_echecs: Number(seuilsDraft.seuil_echecs),
        heure_ouverture: Number(seuilsDraft.heure_ouverture),
        heure_fermeture: Number(seuilsDraft.heure_fermeture),
        seuil_ips_par_user: Number(seuilsDraft.seuil_ips_par_user),
      };
      applyView(await editCyberParams({ seuils }));
    } catch (e) {
      setErr(messageFromCyberError(e, "Échec de l'enregistrement des seuils."));
    } finally {
      setBusy(false);
    }
  }

  async function saveControles() {
    setBusy(true);
    setErr(null);
    try {
      const controles = Object.fromEntries(
        Object.entries(controlesDraft).map(([cle, v]) => [cle, { severite: v.severite, active: v.active }]),
      );
      applyView(await editCyberParams({ controles }));
    } catch (e) {
      setErr(messageFromCyberError(e, "Échec de l'enregistrement de la base de durcissement."));
    } finally {
      setBusy(false);
    }
  }

  async function setValidation(validated: boolean) {
    setBusy(true);
    setErr(null);
    try {
      applyView(await validateCyberParams({ validated, validated_by: validatedBy }));
    } catch (e) {
      setErr(messageFromCyberError(e, "Échec de l'opération de validation."));
    } finally {
      setBusy(false);
    }
  }

  const updControle = (cle: string, patch: Partial<ControleDraft>) =>
    setControlesDraft((s) => ({ ...s, [cle]: { ...s[cle], ...patch } }));

  if (loading) {
    return (
      <Card>
        <Skeleton className="mb-2 h-5 w-1/3" />
        <Skeleton className="h-4 w-full" />
      </Card>
    );
  }

  return (
    <>
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <Card className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {view?.validated ? (
              <span className="flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
                <ShieldCheck className="h-3.5 w-3.5" /> validé
              </span>
            ) : (
              <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
                <ShieldAlert className="h-3.5 w-3.5" /> à valider
              </span>
            )}
            <span className="text-xs text-muted">({view?.source_donnees === "tenant" ? "édité" : "par défaut"})</span>
            {view?.validated && view.validated_by && (
              <span className="text-xs text-muted">
                — validé par {view.validated_by}
                {view.validated_at ? ` le ${new Date(view.validated_at).toLocaleDateString("fr-FR")}` : ""}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Inp value={validatedBy} onChange={setValidatedBy} placeholder="Validé par (nom)" className="w-40" />
            {view?.validated ? (
              <Button variant="ghost" disabled={busy} onClick={() => setValidation(false)}>Révoquer</Button>
            ) : (
              <Button disabled={busy} onClick={() => setValidation(true)}>Valider</Button>
            )}
          </div>
        </div>
        <p className="flex items-start gap-1.5 text-xs text-muted">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> Toute modification des seuils ou de la base de durcissement invalide la validation en cours (re-validation requise).
        </p>
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold">Seuils de détection</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {SEUIL_FIELDS.map((f) => (
            <label key={f.key} className="flex flex-col gap-1 text-xs text-muted">
              {f.label}
              <Inp type="number" value={seuilsDraft[f.key] ?? ""} onChange={(v) => setSeuilsDraft((s) => ({ ...s, [f.key]: v }))} />
            </label>
          ))}
        </div>
        <div className="flex justify-end border-t border-black/5 pt-3">
          <Button onClick={saveSeuils} disabled={busy}><Save className="h-4 w-4" /> Enregistrer les seuils</Button>
        </div>
      </Card>

      <Card className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold">Base de durcissement</h2>
        <div className="flex flex-col gap-1.5">
          {(view?.controles ?? []).map((c) => {
            const draft = controlesDraft[c.cle] ?? { severite: c.severite, active: c.active };
            return (
              <div key={c.cle} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{c.libelle}</div>
                  <div className="text-xs text-muted">{FONCTION_LABELS[c.fonction as Fonction] ?? c.fonction}</div>
                </div>
                <select
                  value={draft.severite}
                  onChange={(e) => updControle(c.cle, { severite: e.target.value as Severite })}
                  className="rounded-lg border border-black/10 bg-white px-2 py-1.5 text-sm"
                >
                  {SEVERITE_OPTIONS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <label className="flex items-center gap-1.5 text-xs">
                  <input
                    type="checkbox"
                    checked={draft.active}
                    onChange={(e) => updControle(c.cle, { active: e.target.checked })}
                  />
                  actif
                </label>
              </div>
            );
          })}
        </div>
        <div className="flex justify-end border-t border-black/5 pt-3">
          <Button onClick={saveControles} disabled={busy}><Save className="h-4 w-4" /> Enregistrer la base de durcissement</Button>
        </div>
      </Card>
    </>
  );
}

// --- primitives --------------------------------------------------------------

function TriState({ value, onChange }: { value: boolean | null; onChange: (v: boolean | null) => void }) {
  const base = "rounded-lg px-2 py-1 text-xs font-medium transition";
  return (
    <div className="ml-auto flex items-center gap-1 shrink-0">
      <button onClick={() => onChange(true)} className={clsx(base, value === true ? "bg-forest text-white" : "bg-black/5 text-ink/60 hover:bg-black/10")}>
        <CheckCircle2 className="h-3.5 w-3.5" />
      </button>
      <button onClick={() => onChange(false)} className={clsx(base, value === false ? "bg-red-600 text-white" : "bg-black/5 text-ink/60 hover:bg-black/10")}>
        <XCircle className="h-3.5 w-3.5" />
      </button>
      <button onClick={() => onChange(null)} className={clsx(base, value === null ? "bg-gray-400 text-white" : "bg-black/5 text-ink/60 hover:bg-black/10")}>
        <HelpCircle className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

const NIVEAU_MAP: Record<string, { c: string; t: string }> = {
  critical: { c: "bg-red-100 text-red-700", t: "Critique" },
  high: { c: "bg-orange-100 text-orange-700", t: "Élevé" },
  medium: { c: "bg-amber-100 text-amber-800", t: "Moyen" },
  low: { c: "bg-emerald-100 text-emerald-700", t: "Faible" },
  aucun: { c: "bg-mint/25 text-forest", t: "Aucun" },
};

function NiveauBadge({ niveau }: { niveau: string }) {
  const m = NIVEAU_MAP[niveau] ?? { c: "bg-gray-100 text-gray-600", t: niveau };
  return <span className={clsx("w-fit rounded-full px-2.5 py-0.5 text-xs font-semibold", m.c)}>Niveau {m.t}</span>;
}

const STATUT_MAP: Record<string, { c: string; t: string }> = {
  conforme: { c: "bg-emerald-100 text-emerald-700", t: "Conforme" },
  non_conforme: { c: "bg-red-100 text-red-700", t: "Non conforme" },
  a_verifier: { c: "bg-gray-100 text-gray-600", t: "À vérifier" },
};

function StatutBadge({ statut }: { statut: string }) {
  const m = STATUT_MAP[statut] ?? { c: "bg-gray-100 text-gray-600", t: statut };
  return <span className={clsx("w-fit rounded-full px-2.5 py-0.5 text-xs font-semibold", m.c)}>{m.t}</span>;
}

function ScoreDial({ score }: { score: number }) {
  const s = Number.isFinite(score) ? score : 0;
  const color = s >= 80 ? "#1E6B4F" : s >= 50 ? "#D9822B" : "#DC2626";
  return (
    <div className="relative grid h-24 w-24 place-items-center rounded-full"
      style={{ background: `conic-gradient(${color} ${s * 3.6}deg, #E9ECF1 0deg)` }}>
      <div className="grid h-[76px] w-[76px] place-items-center rounded-full bg-white">
        <div className="text-2xl font-bold leading-none text-ink">{s.toFixed(0)}%</div>
        <div className="text-xs font-semibold" style={{ color }}>Conformité</div>
      </div>
    </div>
  );
}

const DETECTION_NIVEAU_MAP: Record<string, { c: string; t: string }> = {
  alerte: { c: "bg-red-100 text-red-700", t: "Alerte" },
  attention: { c: "bg-amber-100 text-amber-800", t: "Attention" },
  info: { c: "bg-gray-100 text-gray-600", t: "Info" },
  aucun: { c: "bg-mint/25 text-forest", t: "Aucun" },
};

function DetectionNiveauBadge({ niveau }: { niveau: string }) {
  const m = DETECTION_NIVEAU_MAP[niveau] ?? { c: "bg-gray-100 text-gray-600", t: niveau };
  return <span className={clsx("w-fit rounded-full px-2.5 py-0.5 text-xs font-semibold", m.c)}>{m.t}</span>;
}

const DETECTION_STATUT_MAP: Record<string, { c: string; t: string }> = {
  a_examiner: { c: "bg-amber-100 text-amber-800", t: "À examiner" },
  classee: { c: "bg-black/5 text-ink/60", t: "Classée sans suite" },
  traitee: { c: "bg-forest text-white", t: "Traitée" },
};

function DetectionStatutBadge({ statut }: { statut: string }) {
  const m = DETECTION_STATUT_MAP[statut] ?? { c: "bg-gray-100 text-gray-600", t: statut };
  return <span className={clsx("w-fit rounded-full px-2.5 py-0.5 text-xs font-semibold", m.c)}>{m.t}</span>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div><div className="text-xs text-muted">{label}</div><div className="font-semibold tabular-nums text-ink">{value}</div></div>;
}

function MiniBtn({ onClick, tone, children }: { onClick: () => void; tone: "forest" | "red"; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={clsx("rounded-lg px-2.5 py-1 text-xs font-medium transition", tone === "forest" ? "bg-forest/10 text-forest hover:bg-forest/20" : "bg-red-50 text-red-600 hover:bg-red-100")}>
      {children}
    </button>
  );
}
