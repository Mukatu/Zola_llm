"use client";

import { useState } from "react";
import { Wrench, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { facilityEcheancier, type AssetInput, type EcheanceInput, type FacilityAlerte } from "@/lib/erp";
import { ApiError } from "@/lib/api";

const ASSETS: AssetInput[] = [
  { id_externe: "V1", libelle: "Camion livraison", maintenance_intervalle_jours: 90, derniere_maintenance: "2026-03-01" },
  { id_externe: "G1", libelle: "Groupe électrogène", maintenance_intervalle_jours: 30, derniere_maintenance: "2026-05-20" },
];
const ECHE: EcheanceInput[] = [
  { id_externe: "E1", type_echeance: "assurance", libelle: "Assurance flotte", date_echeance: "2026-07-05" },
  { id_externe: "E2", type_echeance: "visite_technique", libelle: "VT camion", date_echeance: "2026-06-25" },
];

export function FacilityScreen() {
  const [assets, setAssets] = useState<AssetInput[]>(ASSETS);
  const [eche, setEche] = useState<EcheanceInput[]>(ECHE);
  const [res, setRes] = useState<{ maintenances: FacilityAlerte[]; echeances: FacilityAlerte[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const setA = (i: number, k: keyof AssetInput, v: string) =>
    setAssets((l) => l.map((r, j) => (j === i ? { ...r, [k]: k === "maintenance_intervalle_jours" ? Number(v) : v } : r)));
  const setE = (i: number, k: keyof EcheanceInput, v: string) =>
    setEche((l) => l.map((r, j) => (j === i ? { ...r, [k]: v } : r)));

  async function run() {
    setErr(null); setRes(null);
    try { setRes(await facilityEcheancier(assets, eche)); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible."); }
  }

  const items = res ? [...res.maintenances, ...res.echeances].sort((a, b) => a.jours_restants - b.jours_restants) : [];

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Wrench} title="Moyens Généraux — Échéancier" subtitle="Maintenance préventive + échéances (assurances/visites/licences)." />

      <Card>
        <h2 className="mb-2 text-sm font-semibold">Actifs (maintenance préventive)</h2>
        {assets.map((r, i) => (
          <div key={i} className="mt-1 grid grid-cols-[1fr_90px_130px_32px] gap-2">
            <Inp value={r.libelle} onChange={(v) => setA(i, "libelle", v)} />
            <Inp value={r.maintenance_intervalle_jours} type="number" onChange={(v) => setA(i, "maintenance_intervalle_jours", v)} />
            <Inp value={r.derniere_maintenance ?? ""} type="date" onChange={(v) => setA(i, "derniere_maintenance", v)} />
            <button onClick={() => setAssets((l) => l.filter((_, j) => j !== i))} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        <Button variant="ghost" onClick={() => setAssets((l) => [...l, { id_externe: `A${l.length + 1}`, libelle: "", maintenance_intervalle_jours: 90, derniere_maintenance: null }])}>
          <Plus className="h-4 w-4" /> Actif
        </Button>
        <h2 className="mb-2 mt-4 text-sm font-semibold">Échéances</h2>
        {eche.map((r, i) => (
          <div key={i} className="mt-1 grid grid-cols-[1fr_130px_130px_32px] gap-2">
            <Inp value={r.libelle} onChange={(v) => setE(i, "libelle", v)} />
            <Inp value={r.type_echeance} onChange={(v) => setE(i, "type_echeance", v)} />
            <Inp value={r.date_echeance} type="date" onChange={(v) => setE(i, "date_echeance", v)} />
            <button onClick={() => setEche((l) => l.filter((_, j) => j !== i))} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        <div className="mt-3 flex justify-end"><Button onClick={run}>Calculer l'échéancier</Button></div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {res && (
        <Card>
          {items.length === 0 && <p className="text-sm text-muted">Rien dans l'horizon.</p>}
          {items.map((a) => (
            <div key={a.categorie + a.reference} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span className="flex items-center gap-2"><Urg level={a.urgence} /> {a.libelle}</span>
              <span className="text-muted">{a.date_cible} · {a.jours_restants < 0 ? `${-a.jours_restants} j de retard` : `dans ${a.jours_restants} j`}</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
