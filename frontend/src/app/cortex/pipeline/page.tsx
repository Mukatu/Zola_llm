"use client";

// Pipeline commercial (CRM) — cockpit cabinet Zolacortex : suivi des opportunités
// (prospects et clients existants) du lead jusqu'à la conversion en mission.
import { useEffect, useState } from "react";
import Link from "next/link";
import { Target, TrendingUp, Trophy, Plus, RefreshCw, ArrowRight, CheckCircle2, Sparkles, Save } from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import {
  createOpportunity,
  listOpportunities,
  getSummary,
  updateOpportunity,
  convertOpportunity,
  draftProposal,
  type Opportunity,
  type Summary,
  type Stage,
  type CreateOpportunityInput,
} from "@/lib/cortex-pipeline";
import { listClients, type Tenant } from "@/lib/cortex-clients";

const OFFRES = ["conformite_rh", "fiscal_ohada", "tresorerie", "audit_sante", "audit_commercial", "audit_hse_gouvernance"];

const STAGES: Stage[] = ["lead", "qualified", "proposal", "won", "lost"];

const STAGE_LABEL: Record<Stage, string> = {
  lead: "Prospect",
  qualified: "Qualifié",
  proposal: "Proposition",
  won: "Gagné",
  lost: "Perdu",
};

const STAGE_TONE: Record<Stage, BadgeTone> = {
  lead: "grey",
  qualified: "blue",
  proposal: "amber",
  won: "green",
  lost: "red",
};

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Accès réservé.";
  return fallback;
}

function fmtMoney(n: number, cur: string): string {
  return new Intl.NumberFormat("fr-FR").format(n) + " " + cur;
}

function fmtDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("fr-FR");
}

const EMPTY_FORM: CreateOpportunityInput = { title: "", offre: OFFRES[0], amount_estimate: 0, expected_close_date: "", notes: "" };

function ProposalSection({ opportunity, onUpdated }: { opportunity: Opportunity; onUpdated: (o: Opportunity) => void }) {
  const [text, setText] = useState(opportunity.proposal);
  const [saving, setSaving] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "amber"; text: string } | null>(null);

  useEffect(() => {
    setText(opportunity.proposal);
  }, [opportunity.proposal]);

  async function save() {
    setSaving(true);
    try {
      const updated = await updateOpportunity(opportunity.id, { proposal: text });
      onUpdated(updated);
      setMsg(null);
    } catch (e) {
      setMsg({ tone: "amber", text: messageFromError(e, "Échec de l'enregistrement.") });
    } finally {
      setSaving(false);
    }
  }

  async function draftWithAI() {
    setDrafting(true);
    setMsg(null);
    try {
      const result = await draftProposal(opportunity.id, { apply: true });
      if (result.status === "generated") {
        onUpdated({ ...opportunity, proposal: result.content });
        setText(result.content);
        setMsg({ tone: "success", text: "Proposition générée et citée — à relire (sans chiffrage)." });
      } else if (result.status === "abstained") {
        setMsg({ tone: "amber", text: "Le corpus ne couvre pas ce sujet — rien n'a été rédigé." });
      } else {
        setMsg({ tone: "amber", text: "Assistant IA momentanément indisponible." });
      }
    } catch (e) {
      setMsg({ tone: "amber", text: messageFromError(e, "Assistant IA momentanément indisponible.") });
    } finally {
      setDrafting(false);
    }
  }

  return (
    <details className="border-t border-black/5 pt-2">
      <summary className="cursor-pointer list-none text-xs font-medium text-ink marker:hidden">
        Proposition commerciale
      </summary>
      <div className="mt-2 flex flex-col gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          placeholder="Aucune proposition rédigée pour le moment."
          className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
        />
        {msg && (
          <p className={"text-xs " + (msg.tone === "success" ? "text-forest" : "text-amber-700")}>{msg.text}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={save} disabled={saving}>
            <Save className="h-3.5 w-3.5" /> Enregistrer
          </Button>
          <Button variant="ghost" onClick={draftWithAI} disabled={drafting}>
            <Sparkles className="h-3.5 w-3.5" /> {drafting ? "Rédaction en cours…" : "Rédiger la proposition (IA)"}
          </Button>
        </div>
        <p className="text-xs text-muted">Contexte réglementaire ancré et cité ; le chiffrage reste votre décision.</p>
      </div>
    </details>
  );
}

export default function PipelinePage() {
  const { config, user } = useZola();
  const [opportunities, setOpportunities] = useState<Opportunity[] | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [clients, setClients] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState<CreateOpportunityInput>(EMPTY_FORM);
  const [clientTenantId, setClientTenantId] = useState("");
  const [clientName, setClientName] = useState("");

  const canSeeSummary = hasScope(user, "admin:users");

  async function reload() {
    setLoading(true);
    try {
      const [opps, sum] = await Promise.all([
        listOpportunities(),
        canSeeSummary ? getSummary() : Promise.resolve(null),
      ]);
      setOpportunities(opps);
      setSummary(sum);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Pipeline indisponible (backend cortex requis)."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (config.profil === "cortex") {
      reload();
      listClients("client").then(setClients).catch(() => {});
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil, user]);

  async function create() {
    if (!form.title.trim() || !form.offre) return;
    setBusy(true);
    try {
      const body: CreateOpportunityInput = { ...form };
      if (clientTenantId) body.client_tenant_id = clientTenantId;
      else if (clientName.trim()) body.client_name = clientName.trim();
      if (!body.expected_close_date) delete body.expected_close_date;
      if (!body.notes) delete body.notes;
      await createOpportunity(body);
      setForm(EMPTY_FORM);
      setClientTenantId("");
      setClientName("");
      await reload();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec de création.");
    } finally {
      setBusy(false);
    }
  }

  async function changeStage(id: string, stage: Stage) {
    setBusy(true);
    try {
      await updateOpportunity(id, { stage });
      await reload();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec de mise à jour.");
    } finally {
      setBusy(false);
    }
  }

  function patchOpportunity(updated: Opportunity) {
    setOpportunities((prev) => (prev ? prev.map((o) => (o.id === updated.id ? updated : o)) : prev));
  }

  async function convert(id: string) {
    setBusy(true);
    try {
      await convertOpportunity(id, {});
      await reload();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec de conversion en mission.");
    } finally {
      setBusy(false);
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

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest">
            <Target className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-lg font-semibold">Pipeline commercial</h1>
            <p className="text-sm text-muted">Opportunités, du prospect à la mission.</p>
          </div>
        </div>
        <Button variant="ghost" onClick={reload} disabled={loading}>
          <RefreshCw className={"h-4 w-4" + (loading ? " animate-spin" : "")} /> Rafraîchir
        </Button>
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {canSeeSummary && (
        <>
          {loading && !summary && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          )}
          {summary && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
              <Card className="flex flex-col gap-1 p-3">
                <span className="text-xs text-muted">Pipeline ouvert</span>
                <span className="text-xl font-semibold text-ink">{fmtMoney(summary.open_amount, summary.currency)}</span>
              </Card>
              <Card className="flex flex-col gap-1 p-3 ring-1 ring-primary/30">
                <span className="flex items-center gap-1 text-xs text-muted"><TrendingUp className="h-3.5 w-3.5" /> Prévision pondérée</span>
                <span className="text-xl font-semibold text-primary">{fmtMoney(summary.open_weighted, summary.currency)}</span>
              </Card>
              <Card className="flex flex-col gap-1 p-3">
                <span className="flex items-center gap-1 text-xs text-muted"><Trophy className="h-3.5 w-3.5" /> Gagné</span>
                <span className="text-xl font-semibold text-emerald-700">{fmtMoney(summary.won_amount, summary.currency)}</span>
              </Card>
              <Card className="flex flex-col gap-1 p-3">
                <span className="text-xs text-muted">Taux de conversion</span>
                <span className="text-xl font-semibold text-ink">
                  {summary.win_rate === null ? "—" : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(summary.win_rate * 100) + " %"}
                </span>
              </Card>
            </div>
          )}
        </>
      )}

      <Card className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-ink">Créer une opportunité</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm">
            <span className="mb-1 block font-medium">Titre</span>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              placeholder="Ex. Audit conformité RH"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Offre</span>
            <select
              value={form.offre}
              onChange={(e) => setForm({ ...form, offre: e.target.value })}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            >
              {OFFRES.map((o) => <option key={o}>{o}</option>)}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Montant estimé (XAF)</span>
            <input
              type="number"
              min={0}
              value={form.amount_estimate}
              onChange={(e) => setForm({ ...form, amount_estimate: Number(e.target.value) })}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Client existant</span>
            <select
              value={clientTenantId}
              onChange={(e) => { setClientTenantId(e.target.value); if (e.target.value) setClientName(""); }}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            >
              <option value="">— prospect (hors annuaire) —</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Ou nom du prospect</span>
            <input
              value={clientName}
              onChange={(e) => { setClientName(e.target.value); if (e.target.value) setClientTenantId(""); }}
              disabled={!!clientTenantId}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm disabled:bg-black/5"
              placeholder="Ex. Société Nouvelle SARL"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Clôture prévue</span>
            <input
              type="date"
              value={form.expected_close_date || ""}
              onChange={(e) => setForm({ ...form, expected_close_date: e.target.value })}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
          <label className="text-sm sm:col-span-2 lg:col-span-3">
            <span className="mb-1 block font-medium">Notes</span>
            <input
              value={form.notes || ""}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
        </div>
        <div>
          <Button onClick={create} disabled={busy || !form.title.trim()}>
            <Plus className="h-4 w-4" /> Créer
          </Button>
        </div>
      </Card>

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-ink">Pipeline par étape</h2>
        {loading && !opportunities && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
          </div>
        )}
        {opportunities && opportunities.length === 0 && !err && (
          <Card><p className="text-sm text-muted">Aucune opportunité pour le moment.</p></Card>
        )}
        {opportunities && opportunities.length > 0 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {STAGES.map((stage) => {
              const items = opportunities.filter((o) => o.stage === stage);
              if (items.length === 0) return null;
              return (
                <div key={stage} className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <Badge tone={STAGE_TONE[stage]}>{STAGE_LABEL[stage]}</Badge>
                    <span className="text-xs text-muted">{items.length}</span>
                  </div>
                  {items.map((o) => (
                    <Card key={o.id} className="flex flex-col gap-2 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-medium text-ink">{o.title}</span>
                        <Badge tone={STAGE_TONE[o.stage]}>{STAGE_LABEL[o.stage]}</Badge>
                      </div>
                      <div className="text-xs text-muted">
                        {o.client_name || (o.client_tenant_id ? o.client_tenant_id.slice(0, 8) + "…" : "—")} · {o.offre}
                      </div>
                      <div className="text-sm text-ink">
                        {fmtMoney(o.amount_estimate, o.currency)}{" "}
                        <span className="text-xs text-muted">(pondéré {fmtMoney(o.weighted, o.currency)})</span>
                      </div>
                      <div className="text-xs text-muted">Clôture prévue : {fmtDate(o.expected_close_date)}</div>
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        <select
                          value={o.stage}
                          onChange={(e) => changeStage(o.id, e.target.value as Stage)}
                          disabled={busy}
                          className="rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
                        >
                          {STAGES.map((s) => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}
                        </select>
                        {o.stage === "won" && o.client_tenant_id && !o.mission_id && (
                          <Button variant="ghost" onClick={() => convert(o.id)} disabled={busy}>
                            <ArrowRight className="h-3.5 w-3.5" /> Convertir en mission
                          </Button>
                        )}
                        {o.mission_id && (
                          <Link href="/cortex/missions" className="flex items-center gap-1 text-xs text-emerald-700 hover:underline">
                            <CheckCircle2 className="h-3.5 w-3.5" /> mission créée
                          </Link>
                        )}
                      </div>
                      <ProposalSection opportunity={o} onUpdated={patchOpportunity} />
                    </Card>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
