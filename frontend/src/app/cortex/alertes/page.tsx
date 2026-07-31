"use client";

// Alertes marge (cockpit cabinet Zolacortex) : détection déterministe des
// missions en marge négative/faible ou en sous-facturation, avec une note de
// pilotage rédigée par l'IA à partir des alertes. Réservé profil cortex +
// admin:users.
import { useEffect, useState } from "react";
import { TrendingDown, Sparkles, Info } from "lucide-react";
import { Card, Button, Badge, Skeleton, SeverityBadge } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import {
  getMarginAlerts,
  getAlertsBrief,
  type AlertsResult,
  type MarginAlertType,
} from "@/lib/cortex-psa";

const TYPE_LABEL: Record<MarginAlertType, string> = {
  marge_negative: "Marge négative",
  marge_faible: "Marge faible",
  sous_facturation: "Sous-facturation",
};

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Réservé aux administrateurs du cabinet.";
  return fallback;
}

function fmtMoney(n: number): string {
  return new Intl.NumberFormat("fr-FR").format(Math.round(n)) + " XAF";
}

export default function AlertesMargePage() {
  const { config, user } = useZola();
  const allowed = config.profil === "cortex" && hasScope(user, "admin:users");

  const [data, setData] = useState<AlertsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [brief, setBrief] = useState<string | null>(null);
  const [briefStatus, setBriefStatus] = useState<"idle" | "generated" | "unavailable" | "empty">("idle");
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefErr, setBriefErr] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      const res = await getMarginAlerts();
      setData(res);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Alertes indisponibles (backend cortex requis)."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (allowed) reload();
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowed]);

  async function requestBrief() {
    setBriefLoading(true);
    setBriefErr(null);
    try {
      const res = await getAlertsBrief();
      setBrief(res.brief);
      setBriefStatus(res.status);
    } catch (e) {
      setBriefErr(messageFromError(e, "Échec de la génération de la note de pilotage."));
    } finally {
      setBriefLoading(false);
    }
  }

  if (config.profil !== "cortex") {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <p className="text-sm text-muted">Réservé au cockpit cabinet.</p>
        </Card>
      </div>
    );
  }

  if (!hasScope(user, "admin:users")) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <p className="text-sm text-muted">Réservé aux administrateurs du cabinet.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest">
            <TrendingDown className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-lg font-semibold">Alertes marge</h1>
            <p className="text-sm text-muted">
              Missions en marge négative, marge faible ou sous-facturation détectées automatiquement.
            </p>
          </div>
        </div>
        <Button variant="ghost" onClick={reload} disabled={loading}>
          Rafraîchir
        </Button>
      </div>

      {err && (
        <Card className="ring-amber-200">
          <p className="text-sm text-amber-700">{err}</p>
        </Card>
      )}

      {loading && !data && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      )}

      {data && (
        <>
          <Card className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <Info className="h-3.5 w-3.5 shrink-0" />
            <span>
              Seuils actifs — marge faible sous {data.thresholds.margin_low_pct} %, alerte WIP au-delà de{" "}
              {fmtMoney(data.thresholds.wip_alert_xaf)}, honoraires minimum {fmtMoney(data.thresholds.min_honoraires_xaf)}.
            </span>
          </Card>

          <Card>
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">Alertes ({data.count})</div>
            </div>

            {data.count === 0 ? (
              <p className="text-sm text-muted">Aucune alerte : marges et facturation sous contrôle.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-black/5 text-left text-xs text-muted">
                      <th className="py-2 pr-3 font-medium">Sévérité</th>
                      <th className="py-2 pr-3 font-medium">Type</th>
                      <th className="py-2 pr-3 font-medium">Mission</th>
                      <th className="py-2 pr-3 font-medium">Message</th>
                      <th className="py-2 pr-3 font-medium">Impact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.alerts.map((a, i) => (
                      <tr key={a.mission_id + "-" + a.type + "-" + i} className="border-b border-black/5 last:border-0">
                        <td className="py-2 pr-3">
                          <SeverityBadge level={a.severity} />
                        </td>
                        <td className="py-2 pr-3">
                          <Badge tone="grey">{TYPE_LABEL[a.type] ?? a.type}</Badge>
                        </td>
                        <td className="py-2 pr-3 text-ink">{a.offre ?? a.mission_id}</td>
                        <td className="py-2 pr-3 text-muted">{a.message}</td>
                        <td className="py-2 pr-3 font-medium text-ink">{fmtMoney(a.impact)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Sparkles className="h-4 w-4" /> Note de pilotage (IA)
              </div>
              <Button onClick={requestBrief} disabled={briefLoading}>
                <Sparkles className="h-4 w-4" /> {briefLoading ? "Rédaction en cours…" : "Note de pilotage (IA)"}
              </Button>
            </div>
            <p className="text-xs text-muted">
              L&apos;assistant rédige une synthèse à partir des alertes ci-dessus. Génération : quelques secondes.
            </p>

            {briefErr && <p className="text-sm text-amber-700">{briefErr}</p>}

            {briefStatus === "unavailable" && !briefErr && (
              <p className="text-sm text-amber-700">Assistant indisponible pour le moment.</p>
            )}
            {briefStatus === "empty" && !briefErr && (
              <p className="text-sm text-muted">Aucune alerte à synthétiser.</p>
            )}
            {briefStatus === "generated" && brief && (
              <div className="rounded-xl bg-black/[0.02] p-4 ring-1 ring-black/5">
                <p className="whitespace-pre-wrap text-sm text-ink">{brief}</p>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
