"use client";

import { useCallback, useEffect, useState } from "react";
import { Handshake, Plus, Trash2, FileCheck2, Clock, TrendingUp } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { fmt } from "@/lib/data";
import { ApiError } from "@/lib/api";
import {
  listOpportunities,
  createOpportunity,
  moveStage,
  deleteOpportunity,
  listQuotes,
  createQuote,
  convertQuote,
  listCustomers,
  createCustomer,
  listInteractions,
  createInteraction,
  crmAnalyzeStore,
  crmForecast,
  type OpportunityRec,
  type QuoteRec,
  type InteractionRec,
  type CrmAnalyze,
  type Forecast,
} from "@/lib/crm";

const STAGES = ["prospection", "qualification", "proposition", "negociation", "gagnee", "perdue"];
const STAGE_LABEL: Record<string, string> = {
  prospection: "Prospection",
  qualification: "Qualification",
  proposition: "Proposition",
  negociation: "Négociation",
  gagnee: "Gagnée",
  perdue: "Perdue",
};
const GRADE: Record<string, string> = {
  A: "bg-emerald-100 text-emerald-700",
  B: "bg-amber-100 text-amber-700",
  C: "bg-orange-100 text-orange-700",
  D: "bg-gray-100 text-gray-600",
};
const PRIO: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-emerald-100 text-emerald-700",
};
const TODAY = new Date().toISOString().slice(0, 10);

// Jeu de démonstration (persisté) — rend le pipeline tangible sur une base vide.
const DEMO_CUSTOMERS = [
  { id_externe: "C1", nom: "Polyclinique Lumière", type: "client", source: "referral", secteur: "Santé" },
  { id_externe: "C2", nom: "Distrib Brazza", type: "prospect", source: "salon", secteur: "Distribution" },
  { id_externe: "C3", nom: "Télécom Sud", type: "prospect", source: "web", secteur: "Télécom" },
];
const DEMO_OPPS = [
  { id_externe: "O1", client: "Polyclinique Lumière", libelle: "Équipement IT", montant_xaf: "3500000", etape: "negociation", date_cloture_prevue: "2026-07-31" },
  { id_externe: "O2", client: "Distrib Brazza", libelle: "Contrat annuel", montant_xaf: "8000000", etape: "proposition", date_cloture_prevue: "2026-08-15" },
  { id_externe: "O3", client: "Télécom Sud", libelle: "Maintenance", montant_xaf: "5000000", etape: "qualification", date_cloture_prevue: "2026-09-30" },
];

export function CrmScreen() {
  const [opps, setOpps] = useState<OpportunityRec[]>([]);
  const [quotes, setQuotes] = useState<QuoteRec[]>([]);
  const [analyze, setAnalyze] = useState<CrmAnalyze | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [selected, setSelected] = useState<OpportunityRec | null>(null);
  const [timeline, setTimeline] = useState<InteractionRec[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState<string | null>(null);

  const [oppForm, setOppForm] = useState({ client: "", libelle: "", montant_xaf: "", date_cloture_prevue: TODAY });
  const [inter, setInter] = useState({ type: "appel", resume: "" });

  const refresh = useCallback(async () => {
    try {
      const [o, q, a, f] = await Promise.all([
        listOpportunities(),
        listQuotes(),
        crmAnalyzeStore(),
        crmForecast(),
      ]);
      setOpps(o.opportunities);
      setQuotes(q.quotes);
      setAnalyze(a);
      setForecast(f);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const openTimeline = useCallback(async (o: OpportunityRec) => {
    setSelected(o);
    try {
      const { interactions } = await listInteractions({ opportunity_id: o.id });
      setTimeline(interactions);
    } catch {
      setTimeline([]);
    }
  }, []);

  async function onDrop(stage: string) {
    const id = drag;
    setDrag(null);
    if (!id) return;
    const opp = opps.find((o) => o.id === id);
    if (!opp || opp.etape === stage) return;
    // optimiste : on déplace tout de suite, puis on persiste et on rafraîchit le scoring
    setOpps((l) => l.map((o) => (o.id === id ? { ...o, etape: stage } : o)));
    try {
      await moveStage(id, stage);
      await refresh();
    } catch {
      setErr("Déplacement impossible (backend).");
      await refresh();
    }
  }

  async function addOpp() {
    if (!oppForm.client || !oppForm.libelle || !oppForm.montant_xaf) return;
    try {
      await createOpportunity({
        id_externe: `O-${Date.now()}`,
        client: oppForm.client,
        libelle: oppForm.libelle,
        montant_xaf: oppForm.montant_xaf,
        etape: "prospection",
        date_cloture_prevue: oppForm.date_cloture_prevue || null,
      });
      setOppForm({ client: "", libelle: "", montant_xaf: "", date_cloture_prevue: oppForm.date_cloture_prevue });
      await refresh();
    } catch {
      setErr("Création impossible (backend/DB).");
    }
  }

  async function delOpp(id: string) {
    try {
      await deleteOpportunity(id);
      if (selected?.id === id) setSelected(null);
      await refresh();
    } catch {
      setErr("Suppression impossible.");
    }
  }

  async function logInteraction() {
    if (!selected || !inter.resume) return;
    try {
      await createInteraction({
        opportunity_id: selected.id,
        type: inter.type,
        date: TODAY,
        resume: inter.resume,
      });
      setInter({ type: inter.type, resume: "" });
      await openTimeline(selected);
      await refresh(); // récence → scoring/relances
    } catch {
      setErr("Journalisation impossible.");
    }
  }

  async function convert(id: string) {
    try {
      await convertQuote(id);
      await refresh();
    } catch (e) {
      setErr(
        e instanceof ApiError && e.status === 422
          ? "Devis non accepté : conversion refusée."
          : e instanceof ApiError && e.status === 409
            ? "Devis déjà converti en facture."
            : "Conversion impossible.",
      );
    }
  }

  async function seedDemo() {
    try {
      for (const c of DEMO_CUSTOMERS) await createCustomer(c);
      for (const o of DEMO_OPPS) await createOpportunity(o);
      await createQuote({
        id_externe: "Q1",
        numero: "DV-2026-001",
        client: "Polyclinique Lumière",
        date_emission: TODAY,
        statut: "accepte",
        lignes: [{ libelle: "Équipement IT", montant_ht_xaf: "3500000" }],
        montant_ht_xaf: "3500000",
        montant_ttc_xaf: "4130000",
      });
      await refresh();
    } catch {
      setErr("Initialisation du jeu de démo impossible (backend/DB).");
    }
  }

  const p = analyze?.pipeline;
  const isEmpty = opps.length === 0 && quotes.length === 0;

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader
        icon={Handshake}
        title="Commercial / CRM"
        subtitle="Pipeline persistant, scoring déterministe, relances et prévision — le registre vivant du commercial."
      />

      {err && (
        <Card className="ring-amber-200">
          <p className="text-sm text-amber-700">{err}</p>
        </Card>
      )}

      {p && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Opportunités ouvertes" value={String(p.nb_open)} />
          <Kpi label="Pipeline (total)" value={fmt(p.total_open_xaf) + " XAF"} />
          <Kpi label="Pondéré" value={fmt(p.weighted_open_xaf) + " XAF"} />
          <Kpi label="Taux de conversion" value={p.win_rate_pct + " %"} />
        </div>
      )}

      {isEmpty && (
        <Card>
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-muted">
              Aucune donnée commerciale. Le pipeline est <b>persistant</b> : chargez un jeu de démo
              ou créez une opportunité.
            </p>
            <Button onClick={seedDemo}>
              <Plus className="h-4 w-4" /> Charger un jeu de démo
            </Button>
          </div>
        </Card>
      )}

      {/* Création rapide d'opportunité */}
      <Card>
        <h2 className="mb-2 text-sm font-semibold">Nouvelle opportunité</h2>
        <div className="grid grid-cols-[1fr_1fr_120px_140px_36px] gap-2">
          <Inp value={oppForm.client} onChange={(v) => setOppForm({ ...oppForm, client: v })} placeholder="Client" />
          <Inp value={oppForm.libelle} onChange={(v) => setOppForm({ ...oppForm, libelle: v })} placeholder="Libellé" />
          <Inp value={oppForm.montant_xaf} type="number" onChange={(v) => setOppForm({ ...oppForm, montant_xaf: v })} placeholder="Montant" />
          <Inp value={oppForm.date_cloture_prevue} type="date" onChange={(v) => setOppForm({ ...oppForm, date_cloture_prevue: v })} />
          <button onClick={addOpp} className="grid place-items-center rounded-lg bg-primary text-white">
            <Plus className="h-4 w-4" />
          </button>
        </div>
      </Card>

      {/* Kanban : drag-stage persisté */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {STAGES.map((stage) => {
          const cards = opps.filter((o) => o.etape === stage);
          return (
            <div
              key={stage}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => onDrop(stage)}
              className="rounded-xl bg-black/[0.03] p-2"
            >
              <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted">
                {STAGE_LABEL[stage]} ({cards.length})
              </div>
              <div className="flex min-h-[40px] flex-col gap-2">
                {cards.map((o) => {
                  const sc = analyze?.scores[o.id];
                  return (
                    <div
                      key={o.id}
                      draggable
                      onDragStart={() => setDrag(o.id)}
                      onClick={() => openTimeline(o)}
                      className={
                        "cursor-grab rounded-lg bg-surface p-2 text-sm shadow-sm ring-1 active:cursor-grabbing " +
                        (selected?.id === o.id ? "ring-primary" : "ring-black/5")
                      }
                    >
                      <div className="flex items-start justify-between gap-1">
                        <div className="font-medium leading-tight">{o.libelle}</div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            delOpp(o.id);
                          }}
                          className="text-muted hover:text-red-600"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <div className="text-xs text-muted">{o.client}</div>
                      <div className="mt-1 flex items-center justify-between">
                        <span className="text-xs font-semibold">{fmt(o.montant_xaf)} XAF</span>
                        {sc && (
                          <span className={"rounded px-1.5 text-[10px] font-bold " + (GRADE[sc.grade] ?? "")}>
                            {sc.grade} · {sc.score}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Prévision pondérée par mois */}
        <Card>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <TrendingUp className="h-4 w-4 text-emerald-600" /> Prévision pondérée
          </div>
          {forecast && forecast.prevision.length === 0 && (
            <p className="text-sm text-muted">Aucune clôture prévue datée.</p>
          )}
          {forecast?.prevision.map((m) => (
            <div key={m.mois} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
              <span>{m.mois}</span>
              <span className="text-muted">
                {fmt(m.pondere_xaf)} / {fmt(m.brut_xaf)} XAF
              </span>
            </div>
          ))}
          {forecast && (
            <div className="mt-2 flex justify-between text-sm font-semibold">
              <span>Total pondéré</span>
              <span>{fmt(forecast.total_pondere_xaf)} XAF</span>
            </div>
          )}
        </Card>

        {/* Relances proactives */}
        <Card>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Clock className="h-4 w-4 text-amber-600" /> Relances à mener ({analyze?.relances.length ?? 0})
          </div>
          {analyze && analyze.relances.length === 0 && (
            <p className="text-sm text-muted">Aucune relance en attente.</p>
          )}
          {analyze?.relances.map((r, i) => (
            <div key={i} className="flex items-start justify-between gap-2 border-b border-black/5 py-1 text-sm last:border-0">
              <span>{r.libelle}</span>
              <span className={"shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold " + (PRIO[r.priorite] ?? "bg-gray-100 text-gray-600")}>
                {r.priorite}
              </span>
            </div>
          ))}
        </Card>

        {/* Timeline d'interactions de l'opportunité sélectionnée */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">
            Interactions {selected ? `· ${selected.libelle}` : ""}
          </h2>
          {!selected && <p className="text-sm text-muted">Cliquez une carte du pipeline.</p>}
          {selected && (
            <>
              <div className="mb-2 grid grid-cols-[90px_1fr_36px] gap-2">
                <select
                  value={inter.type}
                  onChange={(e) => setInter({ ...inter, type: e.target.value })}
                  className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                >
                  {["appel", "email", "visite", "relance", "note"].map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <Inp value={inter.resume} onChange={(v) => setInter({ ...inter, resume: v })} placeholder="Résumé du contact" />
                <button onClick={logInteraction} className="grid place-items-center rounded-lg bg-primary text-white">
                  <Plus className="h-4 w-4" />
                </button>
              </div>
              {timeline.length === 0 && <p className="text-sm text-muted">Aucune interaction journalisée.</p>}
              {timeline.map((it) => (
                <div key={it.id} className="border-b border-black/5 py-1 text-sm last:border-0">
                  <span className="text-xs text-muted">{it.date} · {it.type}</span>
                  <div>{it.resume}</div>
                </div>
              ))}
            </>
          )}
        </Card>
      </div>

      {/* Devis → facture (clôture continue) */}
      {quotes.length > 0 && (
        <Card>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <FileCheck2 className="h-4 w-4 text-primary" /> Devis
          </div>
          {quotes.map((q) => (
            <div key={q.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span>
                <b>{q.numero}</b> · {q.client} · {fmt(q.montant_ttc_xaf)} XAF
                <span className="ml-2 rounded-full bg-black/5 px-2 py-0.5 text-xs">{q.statut}</span>
              </span>
              {q.invoice_id ? (
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">facturé</span>
              ) : (
                <Button variant="ghost" onClick={() => convert(q.id)} disabled={q.statut !== "accepte"}>
                  <FileCheck2 className="h-4 w-4" /> Convertir
                </Button>
              )}
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </Card>
  );
}
