"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { ShieldCheck, ShieldAlert, CheckCircle2, XCircle, HelpCircle, Save, Trash2, Info } from "lucide-react";
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
  type Controle,
  type ConfigAudit,
  type ControleKey,
  type AuditResult,
  type CyberAudit,
  type Fonction,
} from "@/lib/cyber";

const FONCTION_LABELS: Record<Fonction, string> = {
  identify: "Identifier",
  protect: "Protéger",
  detect: "Détecter",
  respond: "Répondre",
  recover: "Rétablir",
};

const FONCTION_ORDER: Fonction[] = ["identify", "protect", "detect", "respond", "recover"];

export function CyberScreen() {
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
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader
        icon={ShieldCheck}
        title="Cyber-défense — Durcissement"
        subtitle="Audit de configuration défensif et déterministe (aucune action offensive) — base indicative CIS / ANSSI / NIST CSF."
      />

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
    </div>
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
