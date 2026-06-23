"use client";

import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { Card } from "../ui";
import { FlagshipHeader } from "./_shared";
import { biKpis, fmt, type Kpi } from "@/lib/data";

// Données d'exemple (en prod : agrégées depuis les connecteurs du client).
const SAMPLE = {
  periode: "2026-T2",
  invoices: [
    { id_externe: "I1", numero: "F1", sens: "vente", tiers: "A", date_emission: "2026-04-01", montant_ht_xaf: "5000000", montant_ttc_xaf: "5900000", payee: false },
    { id_externe: "I2", numero: "F2", sens: "vente", tiers: "B", date_emission: "2026-04-10", montant_ht_xaf: "3000000", montant_ttc_xaf: "3540000", payee: true },
    { id_externe: "I3", numero: "A1", sens: "achat", tiers: "C", date_emission: "2026-04-05", montant_ht_xaf: "2000000", montant_ttc_xaf: "2360000" },
  ],
  transactions: [
    { id_externe: "T1", date_operation: "2026-04-02", libelle: "Encaissement", montant_xaf: "4000000", sens: "credit" },
    { id_externe: "T2", date_operation: "2026-04-06", libelle: "Fournisseur", montant_xaf: "1500000", sens: "debit" },
  ],
  employees: [
    { id_externe: "E1", nom_complet: "A", salaire_base_xaf: "450000" },
    { id_externe: "E2", nom_complet: "B", salaire_base_xaf: "600000" },
    { id_externe: "E3", nom_complet: "C", salaire_base_xaf: "300000" },
  ],
};

const DOMAINE: Record<string, string> = { commercial: "Commercial", finance: "Finance", rh: "RH" };

export function BiScreen() {
  const [kpis, setKpis] = useState<Kpi[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    biKpis(SAMPLE).then((r) => setKpis(r.kpis)).catch(() => setErr("Service indisponible (hors-ligne ?)."));
  }, []);

  const byDomaine = (kpis ?? []).reduce<Record<string, Kpi[]>>((acc, k) => {
    (acc[k.domaine] ??= []).push(k); return acc;
  }, {});

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader icon={BarChart3} title="Pilotage / BI" subtitle="KPIs cross-métiers (déterministes). Le LLM interprète, ne calcule pas." />
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {Object.entries(byDomaine).map(([dom, list]) => (
        <section key={dom}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{DOMAINE[dom] ?? dom}</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {list.map((k) => (
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
