"use client";

import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { Card } from "../ui";
import { FlagshipHeader } from "./_shared";
import { biDashboard, fmt, type Kpi } from "@/lib/data";

const DOMAINE: Record<string, string> = {
  commercial: "Commercial",
  finance: "Finance",
  achats: "Achats",
  supply: "Supply Chain",
  rh: "RH",
};
const ORDRE = ["commercial", "finance", "achats", "supply", "rh"];

export function BiScreen() {
  const [kpis, setKpis] = useState<Kpi[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    biDashboard()
      .then((r) => setKpis(r.kpis))
      .catch(() => setErr("Backend indisponible (DB requise)."));
  }, []);

  const byDomaine = (kpis ?? []).reduce<Record<string, Kpi[]>>((acc, k) => {
    (acc[k.domaine] ??= []).push(k); return acc;
  }, {});

  const allZero = (kpis ?? []).length > 0 && (kpis ?? []).every((k) => Number(k.valeur) === 0);

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={BarChart3} title="Pilotage / BI" subtitle="Cockpit transversal agrégé sur le registre vivant (déterministe). Le LLM interprète, ne calcule pas." />
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {allZero && (
        <Card><p className="text-sm text-muted">Indicateurs à zéro : alimentez les registres (factures, trésorerie, stock, CRM, achats, RH) — le cockpit s&apos;actualise automatiquement.</p></Card>
      )}
      {ORDRE.filter((dom) => byDomaine[dom]).map((dom) => (
        <section key={dom}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{DOMAINE[dom] ?? dom}</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {byDomaine[dom].map((k) => (
              <Card key={k.code}>
                <div className="text-xs text-muted">{k.libelle}</div>
                <div className="mt-1 text-xl font-semibold">
                  {fmt(k.valeur)} <span className="text-sm font-normal text-muted">{k.unite === "XAF" ? "XAF" : k.unite}</span>
                </div>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
