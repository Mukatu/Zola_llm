"use client";

// Tableau de bord de pilotage (cockpit cabinet Zolacortex) : vue d'ensemble
// commerciale, production et finance du cabinet sur une période donnée.
// Réservé profil cortex + admin:users.
import { useEffect, useState } from "react";
import clsx from "clsx";
import { Gauge, Target, Clock, Wallet, TrendingUp, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card, Button, Badge, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { getDashboard, type Dashboard } from "@/lib/cortex-dashboard";

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Accès réservé aux administrateurs.";
  return fallback;
}

function fmtNum(n: number): string {
  return new Intl.NumberFormat("fr-FR").format(n);
}

function fmtMoney(n: number, cur: string): string {
  return fmtNum(n) + " " + cur;
}

function fmtHours(h: number): string {
  return h.toFixed(1) + " h";
}

function pct(n: number | null): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(n) + " %";
}

function currentPeriod(): string {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
}

function occupationHint(occPct: number | null) {
  if (occPct == null) return null;
  if (occPct < 60) return <Badge tone="amber">Sous-occupation</Badge>;
  if (occPct >= 80) return <Badge tone="green">Optimale</Badge>;
  return null;
}

function Kpi({
  label,
  value,
  hint,
  tone = "default",
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "default" | "primary";
  icon?: LucideIcon;
}) {
  return (
    <Card className={clsx("flex flex-col gap-1 p-3", tone === "primary" && "ring-1 ring-primary/30")}>
      <span className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted">
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {label}
      </span>
      <span className={clsx("text-xl font-semibold", tone === "primary" ? "text-primary" : "text-ink")}>{value}</span>
      {hint && <div className="text-xs text-muted">{hint}</div>}
    </Card>
  );
}

function KpiSkeletons({ count }: { count: number }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-20 w-full" />
      ))}
    </div>
  );
}

export default function PilotagePage() {
  const { config, user } = useZola();
  const [period, setPeriod] = useState(currentPeriod);
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const allowed = config.profil === "cortex" && hasScope(user, "admin:users");

  async function reload(p: string) {
    setLoading(true);
    try {
      const res = await getDashboard(p);
      setData(res);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Tableau de bord indisponible (backend cortex requis)."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (allowed) reload(period);
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowed]);

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
          <p className="text-sm text-muted">Accès réservé aux administrateurs.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest">
            <Gauge className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-lg font-semibold">Tableau de bord de pilotage</h1>
            <p className="text-sm text-muted">Vue d&apos;ensemble commerciale, production et finance du cabinet.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="month"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="rounded-xl border border-black/10 bg-surface px-3 py-2 text-sm text-ink"
            aria-label="Période"
          />
          <Button variant="ghost" onClick={() => reload(period)} disabled={loading}>
            <RefreshCw className={"h-4 w-4" + (loading ? " animate-spin" : "")} /> Rafraîchir
          </Button>
        </div>
      </div>

      {err && (
        <Card className="ring-amber-200">
          <p className="text-sm text-amber-700">{err}</p>
        </Card>
      )}

      {loading && !data && (
        <div className="flex flex-col gap-6">
          <KpiSkeletons count={4} />
          <KpiSkeletons count={4} />
          <KpiSkeletons count={6} />
        </div>
      )}

      {data && (
        <>
          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-ink">Commercial</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Kpi label="Pipeline ouvert" value={fmtMoney(data.commercial.open_amount, data.currency)} icon={Target} />
              <Kpi
                label="Prévision pondérée"
                value={fmtMoney(data.commercial.open_weighted, data.currency)}
                tone="primary"
                icon={TrendingUp}
              />
              <Kpi
                label="Taux de conversion"
                value={pct(data.commercial.win_rate === null ? null : data.commercial.win_rate * 100)}
              />
              <Kpi label="Opportunités ouvertes" value={fmtNum(data.commercial.open_count)} />
            </div>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-ink">Production</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Kpi label="Missions actives" value={fmtNum(data.production.active_missions)} icon={Clock} />
              <Kpi label="Consultants actifs" value={fmtNum(data.production.active_consultants)} />
              <Kpi
                label="Heures facturables"
                value={data.production.billable_hours.toFixed(1) + " / " + fmtHours(data.production.worked_hours)}
              />
              <Kpi
                label="Taux d'occupation"
                value={pct(data.production.occupation_pct)}
                hint={occupationHint(data.production.occupation_pct)}
                icon={Gauge}
              />
            </div>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-ink">Finance</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Kpi
                label="Honoraires du mois"
                value={fmtMoney(data.finance.honoraires_period, data.currency)}
                icon={Wallet}
              />
              <Kpi
                label="Marge"
                value={fmtMoney(data.finance.margin_period, data.currency)}
                hint={pct(data.finance.margin_pct)}
                tone="primary"
              />
              <Kpi label="WIP / encours à facturer" value={fmtMoney(data.finance.wip, data.currency)} />
              <Kpi label="Facturé" value={fmtMoney(data.finance.invoiced_period, data.currency)} />
              <Kpi label="Encaissé" value={fmtMoney(data.finance.collected_period, data.currency)} />
              <Kpi
                label="Créances en cours"
                value={fmtMoney(data.finance.outstanding, data.currency)}
                hint={data.finance.outstanding > 0 ? <Badge tone="red">à relancer</Badge> : null}
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
