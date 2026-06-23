"use client";

import { useEffect, useState } from "react";
import { Handshake } from "lucide-react";
import { Card } from "../ui";
import { FlagshipHeader } from "./_shared";
import { crmAnalyze, fmt, type CrmResult, type OppInput } from "@/lib/data";

const STAGES = ["prospection", "qualification", "proposition", "negociation", "gagnee", "perdue"];
const STAGE_LABEL: Record<string, string> = {
  prospection: "Prospection", qualification: "Qualification", proposition: "Proposition",
  negociation: "Négociation", gagnee: "Gagnée", perdue: "Perdue",
};

const OPPS: OppInput[] = [
  { id_externe: "O1", client: "Polyclinique Lumière", libelle: "Équipement IT", montant_xaf: "3500000", etape: "negociation", derniere_interaction: "2026-06-15" },
  { id_externe: "O2", client: "Distrib Brazza", libelle: "Contrat annuel", montant_xaf: "8000000", etape: "proposition", derniere_interaction: "2026-05-20" },
  { id_externe: "O3", client: "PME Nkayi", libelle: "Audit + conseil", montant_xaf: "1200000", etape: "qualification", derniere_interaction: "2026-06-20" },
  { id_externe: "O4", client: "Télécom Sud", libelle: "Maintenance", montant_xaf: "5000000", etape: "prospection", derniere_interaction: null },
  { id_externe: "O5", client: "ONG Espoir", libelle: "Reporting bailleurs", montant_xaf: "2000000", etape: "gagnee" },
];

const GRADE: Record<string, string> = { A: "bg-emerald-100 text-emerald-700", B: "bg-amber-100 text-amber-700", C: "bg-orange-100 text-orange-700", D: "bg-gray-100 text-gray-600" };

export function CrmScreen() {
  const [res, setRes] = useState<CrmResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    crmAnalyze(OPPS).then(setRes).catch(() => setErr("Service indisponible (hors-ligne ?)."));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={Handshake} title="Commercial / CRM" subtitle="Pipeline, scoring de leads et relances (déterministe)." />

      {res && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Opportunités ouvertes" value={String(res.pipeline.nb_open)} />
          <Kpi label="Pipeline (total)" value={fmt(res.pipeline.total_open_xaf) + " XAF"} />
          <Kpi label="Pondéré" value={fmt(res.pipeline.weighted_open_xaf) + " XAF"} />
          <Kpi label="Taux de conversion" value={res.pipeline.win_rate_pct + " %"} />
        </div>
      )}

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {STAGES.map((stage) => {
          const cards = OPPS.filter((o) => o.etape === stage);
          return (
            <div key={stage} className="rounded-xl bg-black/[0.03] p-2">
              <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted">{STAGE_LABEL[stage]} ({cards.length})</div>
              <div className="flex flex-col gap-2">
                {cards.map((o) => {
                  const sc = res?.scores[o.id_externe];
                  return (
                    <div key={o.id_externe} className="rounded-lg bg-surface p-2 text-sm shadow-sm ring-1 ring-black/5">
                      <div className="font-medium leading-tight">{o.libelle}</div>
                      <div className="text-xs text-muted">{o.client}</div>
                      <div className="mt-1 flex items-center justify-between">
                        <span className="text-xs font-semibold">{fmt(o.montant_xaf)} XAF</span>
                        {sc && <span className={"rounded px-1.5 text-[10px] font-bold " + (GRADE[sc.grade] ?? "")}>{sc.grade} · {sc.score}</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {res && res.relances.length > 0 && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Relances à mener ({res.relances.length})</h2>
          {res.relances.map((r, i) => (
            <div key={i} className="border-b border-black/5 py-1 text-sm last:border-0">• [{r.priorite}] {r.libelle}</div>
          ))}
        </Card>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card><div className="text-xs text-muted">{label}</div><div className="mt-1 text-lg font-semibold">{value}</div></Card>
  );
}
