"use client";

// Supervision de la flotte (cockpit cabinet Zolacortex) : vue d'ensemble des boxes
// clients — connexion, état de licence, missions actives. Lecture seule.
import { useEffect, useState } from "react";
import Link from "next/link";
import { Radar, RefreshCw, Wifi } from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { getFleet, type FleetResponse, type FleetRow, type LicenseStatus } from "@/lib/cortex-fleet";

const LICENSE_TONE: Record<LicenseStatus, BadgeTone> = {
  active: "green", expired: "grey", revoked: "red", none: "grey",
};

const LICENSE_LABEL: Record<LicenseStatus, string> = {
  active: "active", expired: "expirée", revoked: "révoquée", none: "aucune",
};

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Accès réservé aux administrateurs.";
  return fallback;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { year: "numeric", month: "short", day: "numeric" });
}

function ConnectionCell({ row }: { row: FleetRow }) {
  if (!row.box_provisioned) {
    return <span className="flex items-center gap-1.5 text-xs text-muted"><span className="h-2 w-2 rounded-full bg-gray-300" /> box non provisionnée</span>;
  }
  if (row.box_connected) {
    return <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-700"><span className="h-2 w-2 rounded-full bg-emerald-500" /> En ligne</span>;
  }
  return <span className="flex items-center gap-1.5 text-xs text-muted"><span className="h-2 w-2 rounded-full bg-gray-400" /> Hors ligne</span>;
}

function LicenseCell({ row }: { row: FleetRow }) {
  if (row.license_status === "none") {
    return <span className="text-xs text-muted">—</span>;
  }
  const soon = row.license_status === "active" && row.license_days_left !== null && row.license_days_left <= 30;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Badge tone={LICENSE_TONE[row.license_status]}>{LICENSE_LABEL[row.license_status]}</Badge>
      {row.license_tier && <span className="text-xs capitalize text-muted">{row.license_tier}</span>}
      {row.license_status === "active" && row.license_days_left !== null && (
        <span className={"text-xs " + (soon ? "font-semibold text-amber-700" : "text-muted")}>
          expire dans {row.license_days_left} j
        </span>
      )}
      {row.license_status !== "active" && row.license_expires_at && (
        <span className="text-xs text-muted">le {fmtDate(row.license_expires_at)}</span>
      )}
    </div>
  );
}

export default function SupervisionPage() {
  const { config, user } = useZola();
  const [data, setData] = useState<FleetResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      const res = await getFleet(30);
      setData(res);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Supervision indisponible (backend cortex requis)."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (config.profil === "cortex" && hasScope(user, "admin:users")) reload();
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

  const summary = data?.summary;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Radar className="h-5 w-5" /></span>
          <div>
            <h1 className="text-lg font-semibold">Supervision</h1>
            <p className="text-sm text-muted">État de la flotte des boxes clients — connexion, licence, missions.</p>
          </div>
        </div>
        <Button variant="ghost" onClick={reload} disabled={loading}>
          <RefreshCw className={"h-4 w-4" + (loading ? " animate-spin" : "")} /> Rafraîchir
        </Button>
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {loading && !data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      )}

      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted">Clients</span>
            <span className="text-xl font-semibold text-ink">{summary.clients}</span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="flex items-center gap-1 text-xs text-muted"><Wifi className="h-3 w-3" /> En ligne</span>
            <span className="text-xl font-semibold text-ink">{summary.boxes_connected}</span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted">Licences actives</span>
            <span className="text-xl font-semibold text-emerald-700">{summary.licenses_active}</span>
          </Card>
          <Card className={"flex flex-col gap-1 p-3" + (summary.licenses_expiring_soon > 0 ? " ring-amber-200" : "")}>
            <span className="text-xs text-muted">Expirent bientôt</span>
            <span className={"text-xl font-semibold " + (summary.licenses_expiring_soon > 0 ? "text-amber-700" : "text-ink")}>
              {summary.licenses_expiring_soon}
            </span>
          </Card>
          <Card className={"flex flex-col gap-1 p-3" + (summary.licenses_expired_or_revoked > 0 ? " ring-red-200" : "")}>
            <span className="text-xs text-muted">Expirées / révoquées</span>
            <span className={"text-xl font-semibold " + (summary.licenses_expired_or_revoked > 0 ? "text-red-700" : "text-ink")}>
              {summary.licenses_expired_or_revoked}
            </span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted">Sans licence</span>
            <span className="text-xl font-semibold text-muted">{summary.licenses_none}</span>
          </Card>
        </div>
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
          <p className="text-sm text-muted">Aucun client à superviser.</p>
        )}
        {data && data.rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-black/5 text-left text-xs text-muted">
                  <th className="py-2 pr-3 font-medium">Client</th>
                  <th className="py-2 pr-3 font-medium">Connexion</th>
                  <th className="py-2 pr-3 font-medium">Licence</th>
                  <th className="py-2 pr-3 font-medium">Missions actives</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.tenant_id} className="border-b border-black/5 last:border-0">
                    <td className="py-2 pr-3">
                      <Link href={"/cortex/clients/" + row.tenant_id} className="font-medium text-primary hover:underline">
                        {row.name}
                      </Link>
                      <div className="text-xs text-muted">{row.country.toUpperCase()}</div>
                    </td>
                    <td className="py-2 pr-3"><ConnectionCell row={row} /></td>
                    <td className="py-2 pr-3"><LicenseCell row={row} /></td>
                    <td className="py-2 pr-3 text-sm text-ink">{row.active_missions}</td>
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
