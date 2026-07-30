"use client";

// Usage & facturation (cockpit cabinet Zolacortex) : consommation et coût par tenant
// sur une période donnée. Lecture seule.
import { useEffect, useState } from "react";
import Link from "next/link";
import { Receipt, RefreshCw } from "lucide-react";
import { Card, Button, Badge, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { getBilling, type BillingResponse, type BillingRow } from "@/lib/cortex-billing";

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

function currentPeriod(): string {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
}

function CostCell({ row, currency }: { row: BillingRow; currency: string }) {
  const c = row.cost;
  return (
    <details>
      <summary className="cursor-pointer list-none font-medium text-ink marker:hidden">
        {fmtMoney(c.total, currency)}
      </summary>
      <div className="mt-1 flex flex-col gap-0.5 text-xs text-muted">
        <span>Forfait : {fmtMoney(c.monthly_base, currency)}</span>
        <span>Inclus : {fmtNum(c.included_requests)} requêtes</span>
        <span>
          Dépassement : {fmtNum(c.overage_requests)} req. × {fmtMoney(c.overage_per_1k, currency)}/1k ={" "}
          {fmtMoney(c.overage_cost, currency)}
        </span>
      </div>
    </details>
  );
}

export default function FacturationPage() {
  const { config, user } = useZola();
  const [period, setPeriod] = useState(currentPeriod);
  const [data, setData] = useState<BillingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  async function reload(p: string) {
    setLoading(true);
    try {
      const res = await getBilling(p);
      setData(res);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Facturation indisponible (backend cortex requis)."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (config.profil === "cortex" && hasScope(user, "admin:users")) reload(period);
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil, user]);

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

  const allZero = !!data && data.rows.length > 0 && data.rows.every((r) => r.cost.total === 0);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Receipt className="h-5 w-5" /></span>
          <div>
            <h1 className="text-lg font-semibold">Usage &amp; facturation</h1>
            <p className="text-sm text-muted">Consommation et coût par client sur la période sélectionnée.</p>
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

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {loading && !data && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted">Total requêtes</span>
            <span className="text-xl font-semibold text-ink">{fmtNum(data.total_requests)}</span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted">Total tokens</span>
            <span className="text-xl font-semibold text-ink">{fmtNum(data.total_tokens)}</span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted">Total facturé</span>
            <span className="text-xl font-semibold text-emerald-700">{fmtMoney(data.total_cost, data.currency)}</span>
          </Card>
        </div>
      )}

      {allZero && (
        <Card className="ring-blue-200">
          <p className="text-sm text-muted">
            Barème non configuré — l&apos;usage est mesuré mais aucun tarif n&apos;est appliqué (défini via BILLING_PRICING_JSON).
          </p>
        </Card>
      )}

      <Card>
        {loading && !data && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        )}
        {!loading && data && data.rows.length === 0 && !err && (
          <p className="text-sm text-muted">Aucun usage sur cette période.</p>
        )}
        {data && data.rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-black/5 text-left text-xs text-muted">
                  <th className="py-2 pr-3 font-medium">Client</th>
                  <th className="py-2 pr-3 font-medium">Palier</th>
                  <th className="py-2 pr-3 font-medium">Requêtes</th>
                  <th className="py-2 pr-3 font-medium">Tokens</th>
                  <th className="py-2 pr-3 font-medium">Coût</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.tenant_id} className="border-b border-black/5 last:border-0 align-top">
                    <td className="py-2 pr-3">
                      {row.name ? (
                        <Link href={"/cortex/clients/" + row.tenant_id} className="font-medium text-primary hover:underline">
                          {row.name}
                        </Link>
                      ) : (
                        <span className="text-ink">{row.tenant_id}</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      {row.tier ? <Badge tone="mint">{row.tier}</Badge> : <span className="text-xs text-muted">—</span>}
                    </td>
                    <td className="py-2 pr-3 text-sm text-ink">{fmtNum(row.requests)}</td>
                    <td className="py-2 pr-3 text-sm text-ink">{fmtNum(row.tokens)}</td>
                    <td className="py-2 pr-3 text-sm">
                      <CostCell row={row} currency={data.currency} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
