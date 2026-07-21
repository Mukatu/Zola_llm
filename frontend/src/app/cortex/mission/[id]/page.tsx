"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ShieldCheck, FileText, Gavel, Play, Loader2, AlertTriangle } from "lucide-react";
import { Card, Button, Skeleton, SeverityBadge } from "@/components/ui";
import { ApiError } from "@/lib/api";
import {
  getMission,
  runAudit,
  downloadReport,
  type MissionDetail,
  type AuditResult,
  type Citation,
} from "@/lib/cortex";

const STATUS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700", revoked: "bg-red-100 text-red-700",
  expired: "bg-gray-100 text-gray-600", completed: "bg-blue-100 text-blue-700",
};

// Audit actuellement affiché : celui déjà enregistré sur la mission (last_audit)
// ou celui qu'on vient de lancer (même forme, sans la requête pour ce dernier cas).
interface AuditView {
  query?: string;
  ran_at: string;
  result: AuditResult;
  citations: Citation[];
}

// snake_case → libellé lisible ("risque_prudhommal" → "Risque prudhommal").
// Les clés des findings dépendent de l'offre : jamais de mapping figé ici.
function labelize(key: string): string {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function severityOf(finding: Record<string, unknown>): string | undefined {
  const v = finding.severite ?? finding.severity;
  return typeof v === "string" ? v : undefined;
}

interface AuditErrorInfo { insufficientContext: boolean; message: string }

// Traduit les codes d'erreur backend (detail JSON `{"detail": "..."}`) en messages FR.
// insufficient_context est un garde-fou volontaire ("je cite, je ne tranche pas"),
// pas une panne : il est présenté distinctement (encart ambre positif).
function parseAuditError(e: unknown): AuditErrorInfo {
  if (!(e instanceof ApiError)) return { insufficientContext: false, message: "Service d'audit indisponible." };
  let detail = e.detail;
  try {
    const parsed = JSON.parse(e.detail) as { detail?: string };
    if (parsed?.detail) detail = parsed.detail;
  } catch {
    /* detail n'est pas du JSON — on garde le texte brut */
  }
  if (detail.includes("insufficient_context")) {
    return {
      insufficientContext: true,
      message:
        "Le corpus disponible n'est pas assez proche pour étayer un audit fiable — l'agent s'abstient plutôt que d'extrapoler. Précisez la requête d'audit.",
    };
  }
  if (detail.includes("unknown_offre")) return { insufficientContext: false, message: "Cette offre n'a pas (encore) de méthodologie d'audit associée." };
  if (detail.includes("mission_revoked")) return { insufficientContext: false, message: "Mission révoquée : audit impossible." };
  if (detail.includes("mission_expired")) return { insufficientContext: false, message: "Mission expirée : audit impossible." };
  if (detail.includes("overlay_output_invalid")) return { insufficientContext: false, message: "Sortie du modèle non conforme au format attendu — réessayez." };
  if (e.status === 403) return { insufficientContext: false, message: "Accès réservé au cabinet propriétaire de la mission." };
  return { insufficientContext: false, message: "Échec de l'audit." };
}

function messageFromReportError(e: unknown): string {
  if (!(e instanceof ApiError)) return "Téléchargement du rapport impossible.";
  let detail = e.detail;
  try {
    const parsed = JSON.parse(e.detail) as { detail?: string };
    if (parsed?.detail) detail = parsed.detail;
  } catch {
    /* texte brut */
  }
  if (detail.includes("no_audit_yet")) return "Lancez d'abord un audit.";
  if (e.status === 403) return "Accès réservé au cabinet propriétaire de la mission.";
  return "Téléchargement du rapport impossible.";
}

export default function MissionCockpit() {
  const { id } = useParams<{ id: string }>();
  const [mission, setMission] = useState<MissionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  const [auditQuery, setAuditQuery] = useState("");
  const [deep, setDeep] = useState(false);
  const [audit, setAudit] = useState<AuditView | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditErr, setAuditErr] = useState<string | null>(null);
  const [insufficientContext, setInsufficientContext] = useState(false);

  const [reportLoading, setReportLoading] = useState(false);
  const [reportErr, setReportErr] = useState<string | null>(null);

  useEffect(() => {
    getMission(id)
      .then((m) => {
        setMission(m);
        if (m.last_audit) setAudit(m.last_audit);
      })
      .catch(() => setLoadErr("Cortex injoignable / authentification requise."))
      .finally(() => setLoading(false));
  }, [id]);

  async function launchAudit() {
    setAuditLoading(true);
    setAuditErr(null);
    setInsufficientContext(false);
    try {
      const res = await runAudit(id, { query: auditQuery.trim() || undefined, deep });
      setAudit({ query: auditQuery.trim() || undefined, ran_at: res.ran_at, result: res.result, citations: res.citations });
    } catch (e) {
      const info = parseAuditError(e);
      setInsufficientContext(info.insufficientContext);
      setAuditErr(info.message);
    } finally {
      setAuditLoading(false);
    }
  }

  async function generateReport() {
    setReportLoading(true);
    setReportErr(null);
    try {
      await downloadReport(id);
    } catch (e) {
      setReportErr(messageFromReportError(e));
    } finally {
      setReportLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Link href="/cortex/missions" className="flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> Missions</Link>

      {loading && <Card><Skeleton className="mb-2 h-5 w-1/3" /><Skeleton className="h-4 w-2/3" /></Card>}
      {loadErr && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{loadErr}</p></Card>}

      {mission && (
        <>
          <Card>
            <div className="flex items-center justify-between gap-2">
              <h1 className="text-lg font-semibold">{mission.offre}</h1>
              <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (STATUS[mission.status] ?? "bg-gray-100")}>{mission.status}</span>
            </div>
            <div className="mt-1 grid gap-1 text-sm text-muted">
              <span>Client : {mission.client_tenant_id}</span>
              <span>
                Démarrée {new Date(mission.started_at).toLocaleString("fr-FR")} · expire {new Date(mission.expires_at).toLocaleString("fr-FR")}
                {mission.revoked_at ? " · révoquée " + new Date(mission.revoked_at).toLocaleString("fr-FR") : ""}
              </span>
              <span>Scope : {mission.scope_tags.join(", ")}</span>
            </div>
          </Card>

          <Card className="flex items-start gap-3 text-sm text-muted">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <span>Pendant cette mission, les méthodologies cabinet s'exécutent <b className="text-ink">chez Polaris</b> ; seuls des extraits <b className="text-ink">anonymisés</b> de la Zolabox du client transitent (scopés, audités). Aucune donnée brute client ne quitte ses murs.</span>
          </Card>

          <Card className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Gavel className="h-5 w-5" /></span>
              <div className="flex-1"><div className="font-semibold">Audit</div><div className="text-xs text-muted">Méthodologie d'audit de l'offre, exécutée sur le corpus scopé de la mission.</div></div>
            </div>

            <textarea
              value={auditQuery}
              onChange={(e) => setAuditQuery(e.target.value)}
              placeholder="Requête d'audit (optionnel) — laissez vide pour un balayage par défaut selon l'offre."
              rows={3}
              disabled={auditLoading}
              className="w-full resize-y rounded-xl border border-black/10 bg-white p-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            />
            <label className="flex items-center gap-2 text-sm text-muted">
              <input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} disabled={auditLoading} />
              Analyse approfondie (70B, plus lent)
            </label>

            <div className="flex items-center gap-3">
              <Button onClick={launchAudit} disabled={auditLoading || mission.status !== "active"}>
                {auditLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Lancer l'audit
              </Button>
              {mission.status !== "active" && <span className="text-xs text-muted">Mission non active — audit indisponible.</span>}
            </div>

            {auditLoading && (
              <div className="flex items-center gap-2 text-sm text-muted">
                <Loader2 className="h-4 w-4 animate-spin" /> Audit en cours… le modèle analyse le corpus (jusqu'à une minute, plus en analyse approfondie).
              </div>
            )}

            {auditErr && (
              <div className={"flex items-start gap-2 rounded-xl p-3 text-sm ring-1 " + (insufficientContext ? "ring-amber-200 text-amber-700" : "ring-red-200 text-red-700")}>
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{auditErr}</span>
              </div>
            )}
          </Card>

          {audit && <AuditPanel audit={audit} />}

          <Card className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><FileText className="h-5 w-5" /></span>
            <div className="flex-1">
              <div className="font-semibold">Rapport</div>
              <div className="text-xs text-muted">{audit ? "Générer le livrable .docx à partir du dernier audit." : "Lancez d'abord un audit pour pouvoir générer un rapport."}</div>
              {reportErr && <div className="mt-1 text-xs text-red-600">{reportErr}</div>}
            </div>
            <Button variant="ghost" onClick={generateReport} disabled={!audit || reportLoading}>
              {reportLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              Générer
            </Button>
          </Card>

          <p className="text-xs text-muted">Les méthodologies d'audit (overlays) et la génération de rapports sont servies par le déploiement Cortex (composants cabinet, non publics).</p>
        </>
      )}
    </div>
  );
}

function AuditPanel({ audit }: { audit: AuditView }) {
  const findings = audit.result.findings ?? [];
  return (
    <div className="flex flex-col gap-3">
      <Card>
        <div className="mb-1 text-xs text-muted">Audit du {new Date(audit.ran_at).toLocaleString("fr-FR")}</div>
        <p className="text-sm">{audit.result.synthese}</p>
      </Card>

      {findings.length > 0 && (
        <div className="flex flex-col gap-2">
          {findings.map((f, i) => {
            const sev = severityOf(f);
            return (
              <Card key={i}>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-sm font-semibold">Constat {i + 1}</span>
                  {sev && <SeverityBadge level={sev} />}
                </div>
                <dl className="grid gap-1 text-sm">
                  {Object.entries(f)
                    .filter(([k]) => k !== "severity" && k !== "severite")
                    .map(([k, v]) => (
                      <div key={k} className="flex gap-2">
                        <dt className="shrink-0 font-medium text-muted">{labelize(k)}</dt>
                        <dd className="text-ink">{typeof v === "string" ? v : JSON.stringify(v)}</dd>
                      </div>
                    ))}
                </dl>
              </Card>
            );
          })}
        </div>
      )}

      {audit.citations.length > 0 && (
        <Card className="flex flex-col gap-1 text-xs text-muted">
          <span className="font-medium text-ink">Sources</span>
          {audit.citations.map((c) => (
            <span key={c.index}>[{c.index}] {c.source_uri} {c.source_id ? "· " + c.source_id : ""} · similarité {(c.similarity * 100).toFixed(0)}%</span>
          ))}
        </Card>
      )}
    </div>
  );
}
