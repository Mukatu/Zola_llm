"use client";

// Facturation d'honoraires (cockpit cabinet Zolacortex) : le cabinet regroupe
// les feuilles de temps facturables approuvées d'une mission en facture,
// suit le cycle draft → issued → paid (ou cancelled), et l'échéancier des
// créances émises (base des relances). Réservé profil cortex + admin:users.
import { useEffect, useState } from "react";
import { Receipt, FileText, AlertTriangle, RefreshCw, Send, CheckCircle2, Ban } from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { listMissions, type MissionSummary } from "@/lib/cortex";
import {
  createInvoice,
  listInvoices,
  getAging,
  getInvoice,
  issueInvoice,
  payInvoice,
  cancelInvoice,
  type Invoice,
  type InvoiceStatus,
  type InvoiceDetail,
  type Aging,
} from "@/lib/cortex-invoices";

const STATUS_TONE: Record<InvoiceStatus, BadgeTone> = {
  draft: "grey",
  issued: "blue",
  paid: "green",
  cancelled: "red",
};

const STATUS_LABEL: Record<InvoiceStatus, string> = {
  draft: "brouillon",
  issued: "émise",
  paid: "payée",
  cancelled: "annulée",
};

const BUCKET_ORDER = ["current", "1-30", "31-60", "61-90", "90+"] as const;
const BUCKET_LABEL: Record<string, string> = {
  current: "À échoir",
  "1-30": "1-30 j",
  "31-60": "31-60 j",
  "61-90": "61-90 j",
  "90+": "+90 j",
};

function bucketTone(bucket: string): "ink" | "amber" | "red" {
  if (bucket === "31-60") return "amber";
  if (bucket === "61-90" || bucket === "90+") return "red";
  return "ink";
}

// Traduit les codes d'erreur backend (detail JSON `{"detail": "..."}`) en messages FR.
function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  let detail = e.detail;
  try {
    const parsed = JSON.parse(e.detail) as { detail?: string };
    if (parsed?.detail) detail = parsed.detail;
  } catch {
    /* detail n'est pas du JSON — on garde le texte brut */
  }
  if (detail.includes("nothing_to_invoice")) {
    return "Aucun temps facturable approuvé à facturer sur cette mission.";
  }
  if (detail.includes("mission_not_found")) return "Mission introuvable.";
  if (detail.includes("invoice_not_found")) return "Facture introuvable.";
  if (detail.includes("not_draft")) return "Cette facture n'est plus au brouillon.";
  if (detail.includes("not_issued")) return "Cette facture n'est pas émise.";
  if (detail.includes("cannot_cancel")) return "Cette facture ne peut plus être annulée.";
  if (e.status === 403) return "Accès réservé aux administrateurs.";
  return fallback;
}

function fmtNum(n: number): string {
  return new Intl.NumberFormat("fr-FR").format(n);
}

function fmtMoney(n: number, cur: string): string {
  return fmtNum(n) + " " + cur;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", { year: "numeric", month: "short", day: "numeric" });
}

function missionLabel(missions: MissionSummary[], missionId: string): string {
  return missions.find((m) => m.mission_id === missionId)?.offre ?? missionId;
}

function InvoiceDetailPanel({
  invoiceId,
  status,
  missions,
  onChanged,
}: {
  invoiceId: string;
  status: InvoiceStatus;
  missions: MissionSummary[];
  onChanged: () => void;
}) {
  const [detail, setDetail] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dueDays, setDueDays] = useState("30");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getInvoice(invoiceId)
      .then((d) => {
        if (alive) {
          setDetail(d);
          setErr(null);
        }
      })
      .catch((e) => {
        if (alive) setErr(messageFromError(e, "Détail de la facture indisponible."));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceId]);

  async function run(action: () => Promise<Invoice>) {
    setBusy(true);
    setErr(null);
    try {
      await action();
      onChanged();
    } catch (e) {
      setErr(messageFromError(e, "Échec de l'opération."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-t border-black/5 bg-black/[0.02] p-4">
      {loading && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
        </div>
      )}
      {err && <p className="mb-2 text-sm text-amber-700">{err}</p>}
      {!loading && detail && (
        <>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
            <FileText className="h-4 w-4" /> Saisies rattachées
          </div>
          {detail.entries.length === 0 ? (
            <p className="mb-3 text-sm text-muted">Aucune saisie rattachée.</p>
          ) : (
            <div className="mb-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-black/5 text-left text-xs text-muted">
                    <th className="py-1.5 pr-3 font-medium">Date</th>
                    <th className="py-1.5 pr-3 font-medium">Activité</th>
                    <th className="py-1.5 pr-3 font-medium">Durée</th>
                    <th className="py-1.5 pr-3 font-medium">Honoraires</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.entries.map((entry) => (
                    <tr key={entry.id} className="border-b border-black/5 last:border-0">
                      <td className="py-1.5 pr-3">{fmtDate(entry.entry_date)}</td>
                      <td className="py-1.5 pr-3">{entry.activity || "—"}</td>
                      <td className="py-1.5 pr-3">{(entry.minutes / 60).toFixed(1)} h</td>
                      <td className="py-1.5 pr-3">{fmtMoney(entry.honoraires, detail.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mb-3 text-xs text-muted">Mission : {missionLabel(missions, detail.mission_id)}</p>

          {status === "draft" && (
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-sm">
                <span className="mr-1.5 text-xs text-muted">Échéance (jours)</span>
                <input
                  type="number"
                  min={0}
                  value={dueDays}
                  onChange={(e) => setDueDays(e.target.value)}
                  className="w-20 rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                />
              </label>
              <Button
                onClick={() => run(() => issueInvoice(invoiceId, { due_days: Number(dueDays) || 30 }))}
                disabled={busy}
              >
                <Send className="h-4 w-4" /> Émettre
              </Button>
              <Button variant="ghost" onClick={() => run(() => cancelInvoice(invoiceId))} disabled={busy}>
                <Ban className="h-4 w-4" /> Annuler
              </Button>
            </div>
          )}
          {status === "issued" && (
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => run(() => payInvoice(invoiceId))} disabled={busy}>
                <CheckCircle2 className="h-4 w-4" /> Encaisser
              </Button>
              <Button variant="ghost" onClick={() => run(() => cancelInvoice(invoiceId))} disabled={busy}>
                <Ban className="h-4 w-4" /> Annuler
              </Button>
            </div>
          )}
          {(status === "paid" || status === "cancelled") && (
            <p className="text-xs text-muted">Aucune action disponible sur cette facture.</p>
          )}
        </>
      )}
    </div>
  );
}

export default function HonorairesPage() {
  const { config, user } = useZola();
  const allowed = config.profil === "cortex" && hasScope(user, "admin:users");

  const [missions, setMissions] = useState<MissionSummary[]>([]);

  const [aging, setAging] = useState<Aging | null>(null);
  const [agingLoading, setAgingLoading] = useState(true);
  const [agingErr, setAgingErr] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "">("");
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [invLoading, setInvLoading] = useState(true);
  const [invErr, setInvErr] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [missionId, setMissionId] = useState("");
  const [notes, setNotes] = useState("");
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);

  async function reloadAging() {
    setAgingLoading(true);
    try {
      const res = await getAging();
      setAging(res);
      setAgingErr(null);
    } catch (e) {
      setAgingErr(messageFromError(e, "Échéancier indisponible (backend cortex requis)."));
    } finally {
      setAgingLoading(false);
    }
  }

  async function reloadInvoices(filter: InvoiceStatus | "" = statusFilter) {
    setInvLoading(true);
    try {
      const rows = await listInvoices(filter ? { status: filter } : {});
      setInvoices(rows);
      setInvErr(null);
    } catch (e) {
      setInvErr(messageFromError(e, "Liste des factures indisponible (backend cortex requis)."));
    } finally {
      setInvLoading(false);
    }
  }

  function reloadAll() {
    reloadAging();
    reloadInvoices();
  }

  useEffect(() => {
    if (!allowed) {
      setAgingLoading(false);
      setInvLoading(false);
      return;
    }
    reloadAging();
    reloadInvoices();
    listMissions()
      .then(setMissions)
      .catch(() => setMissions([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowed]);

  useEffect(() => {
    if (!missionId && missions.length > 0) setMissionId(missions[0].mission_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [missions]);

  async function submitCreate() {
    if (!missionId) {
      setCreateErr("Sélectionnez une mission.");
      return;
    }
    setCreating(true);
    setCreateErr(null);
    try {
      await createInvoice({ mission_id: missionId, notes });
      setNotes("");
      await reloadInvoices();
    } catch (e) {
      setCreateErr(messageFromError(e, "Échec de la création de la facture."));
    } finally {
      setCreating(false);
    }
  }

  function changeFilter(next: InvoiceStatus | "") {
    setStatusFilter(next);
    reloadInvoices(next);
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
          <p className="text-sm text-muted">Accès réservé aux administrateurs.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest">
            <Receipt className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-lg font-semibold">Facturation d&apos;honoraires</h1>
            <p className="text-sm text-muted">Factures cabinet → client, à partir des feuilles de temps approuvées.</p>
          </div>
        </div>
        <Button variant="ghost" onClick={reloadAll} disabled={agingLoading || invLoading}>
          <RefreshCw className={"h-4 w-4" + (agingLoading || invLoading ? " animate-spin" : "")} /> Rafraîchir
        </Button>
      </div>

      {/* --- Échéancier (relances) --- */}
      <Card className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <AlertTriangle className="h-4 w-4" /> Échéancier (relances)
        </div>
        {agingErr && <p className="text-sm text-amber-700">{agingErr}</p>}
        {agingLoading && !aging && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}
        {aging && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
            <div className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
              <div className="text-xs text-muted">Total en cours</div>
              <div className="text-lg font-semibold text-ink">{fmtMoney(aging.total_outstanding, aging.currency)}</div>
            </div>
            {BUCKET_ORDER.map((bucket) => {
              const amount = aging.buckets[bucket] ?? 0;
              const tone = bucketTone(bucket);
              return (
                <div key={bucket} className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
                  <div className="text-xs text-muted">{BUCKET_LABEL[bucket]}</div>
                  <div
                    className={
                      "text-lg font-semibold " +
                      (tone === "red" ? "text-red-700" : tone === "amber" ? "text-amber-700" : "text-ink")
                    }
                  >
                    {fmtMoney(amount, aging.currency)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* --- Créer une facture --- */}
      <Card className="flex flex-col gap-3">
        <div className="text-sm font-semibold">Créer une facture</div>
        {createErr && <p className="text-sm text-amber-700">{createErr}</p>}
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm sm:col-span-1">
            <span className="mb-1 block font-medium">Mission</span>
            {missions.length > 0 ? (
              <select
                value={missionId}
                onChange={(e) => setMissionId(e.target.value)}
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              >
                {missions.map((m) => (
                  <option key={m.mission_id} value={m.mission_id}>
                    {m.offre}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={missionId}
                onChange={(e) => setMissionId(e.target.value)}
                placeholder="id de la mission"
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              />
            )}
          </label>
          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block font-medium">Notes</span>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="facultatif"
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
        </div>
        <div>
          <Button onClick={submitCreate} disabled={creating}>
            <Receipt className="h-4 w-4" /> Générer
          </Button>
        </div>
      </Card>

      {/* --- Liste des factures --- */}
      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold">Factures</div>
          <label className="text-sm">
            <span className="mr-1.5 text-xs text-muted">Statut</span>
            <select
              value={statusFilter}
              onChange={(e) => changeFilter(e.target.value as InvoiceStatus | "")}
              className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            >
              <option value="">Tous</option>
              <option value="draft">Brouillon</option>
              <option value="issued">Émise</option>
              <option value="paid">Payée</option>
              <option value="cancelled">Annulée</option>
            </select>
          </label>
        </div>

        {invErr && <p className="mb-2 text-sm text-amber-700">{invErr}</p>}
        {invLoading && !invoices.length && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        )}
        {!invLoading && invoices.length === 0 && !invErr && (
          <p className="text-sm text-muted">Aucune facture pour le moment.</p>
        )}
        {invoices.length > 0 && (
          <div className="flex flex-col">
            {invoices.map((inv) => {
              const expanded = expandedId === inv.id;
              return (
                <div key={inv.id} className="border-b border-black/5 last:border-0">
                  <button
                    type="button"
                    onClick={() => setExpandedId(expanded ? null : inv.id)}
                    className="grid w-full grid-cols-2 gap-2 py-2.5 text-left text-sm sm:grid-cols-5"
                  >
                    <span className="font-medium text-ink">{inv.number}</span>
                    <span>
                      <Badge tone={STATUS_TONE[inv.status]}>{STATUS_LABEL[inv.status]}</Badge>
                    </span>
                    <span className="text-ink">{fmtMoney(inv.amount, inv.currency)}</span>
                    <span className="text-muted">Échéance : {fmtDate(inv.due_date)}</span>
                    <span className="text-xs text-muted">{missionLabel(missions, inv.mission_id)}</span>
                  </button>
                  {expanded && (
                    <InvoiceDetailPanel
                      invoiceId={inv.id}
                      status={inv.status}
                      missions={missions}
                      onChanged={reloadAll}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
