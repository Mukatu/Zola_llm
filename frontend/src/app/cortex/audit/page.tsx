"use client";

// Journal d'audit (cockpit cabinet Zolacortex) : trace anté-chronologique des
// événements de gouvernance (licences, comptes, boxes, missions...). Lecture seule.
import { useEffect, useState } from "react";
import Link from "next/link";
import { ScrollText, RefreshCw } from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { listAudit, listAuditActions, type AuditEvent } from "@/lib/cortex-audit";

const SEVERITY_TONE: Record<string, BadgeTone> = {
  info: "blue",
  warning: "amber",
  error: "red",
  critical: "red",
};

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Accès réservé aux administrateurs.";
  return fallback;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function summaryOf(ev: AuditEvent): string {
  const s = ev.payload?.summary;
  return typeof s === "string" && s.length > 0 ? s : ev.event;
}

function actorOf(ev: AuditEvent): string {
  const email = ev.payload?.actor_email;
  if (typeof email === "string" && email.length > 0) return email;
  return ev.actor_id ?? ev.actor_type;
}

export default function AuditPage() {
  const { config, user } = useZola();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [actions, setActions] = useState<string[]>([]);
  const [eventFilter, setEventFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      const rows = await listAudit({
        event: eventFilter || undefined,
        category: categoryFilter || undefined,
      });
      setEvents(rows);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Journal d'audit indisponible (backend cortex requis)."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (config.profil === "cortex" && hasScope(user, "admin:users")) {
      listAuditActions()
        .then(setActions)
        .catch(() => setActions([]));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil, user]);

  useEffect(() => {
    if (config.profil === "cortex" && hasScope(user, "admin:users")) reload();
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil, user, eventFilter, categoryFilter]);

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
          <p className="text-sm text-muted">Accès réservé aux administrateurs du cabinet.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest">
            <ScrollText className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-lg font-semibold">Journal d&apos;audit</h1>
            <p className="text-sm text-muted">
              Trace des événements de gouvernance — licences, comptes, boxes, missions.
            </p>
          </div>
        </div>
        <Button variant="ghost" onClick={reload} disabled={loading}>
          <RefreshCw className={"h-4 w-4" + (loading ? " animate-spin" : "")} /> Rafraîchir
        </Button>
      </div>

      <Card className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block font-medium">Type d&apos;action</span>
          <select
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
            className="w-full min-w-[220px] rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          >
            <option value="">Toutes</option>
            {actions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Catégorie</span>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="w-full min-w-[160px] rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          >
            <option value="">Gouvernance</option>
            <option value="all">Tout</option>
          </select>
        </label>
        <Button variant="ghost" onClick={reload} disabled={loading}>
          <RefreshCw className={"h-4 w-4" + (loading ? " animate-spin" : "")} /> Rafraîchir
        </Button>
      </Card>

      {err && (
        <Card className="ring-amber-200">
          <p className="text-sm text-amber-700">{err}</p>
        </Card>
      )}

      <Card>
        {loading && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}
        {!loading && events.length === 0 && !err && (
          <p className="text-sm text-muted">Aucun événement.</p>
        )}
        {!loading && events.length > 0 && (
          <div className="flex flex-col divide-y divide-black/5">
            {events.map((ev) => (
              <div key={ev.id} className="flex flex-col gap-1 py-3 text-sm first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted">{fmtDate(ev.occurred_at)}</span>
                  <Badge tone={SEVERITY_TONE[ev.severity] ?? "grey"}>{ev.severity}</Badge>
                  <span className="font-mono text-xs text-muted">{ev.event}</span>
                  {ev.tenant_id && (
                    <Link
                      href={"/cortex/clients/" + ev.tenant_id}
                      className="text-xs text-primary hover:underline"
                    >
                      client concerné
                    </Link>
                  )}
                </div>
                <p className="font-medium text-ink">{summaryOf(ev)}</p>
                <p className="text-xs text-muted">Par {actorOf(ev)}</p>
                <details className="text-xs text-muted">
                  <summary className="cursor-pointer select-none">Détail</summary>
                  <pre className="mt-1 overflow-x-auto rounded-lg bg-black/5 p-2 text-xs">
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                </details>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
