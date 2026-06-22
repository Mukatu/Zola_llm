"use client";

import { useState } from "react";
import { HardHat, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { hseCartographie, type RisqueInput, type RisqueEvalue } from "@/lib/erp";
import { ApiError } from "@/lib/api";

const DEFAULT: RisqueInput[] = [
  { id_externe: "R1", libelle: "Incendie atelier", probabilite: 2, gravite: 4 },
  { id_externe: "R2", libelle: "Électrocution", probabilite: 5, gravite: 4 },
  { id_externe: "R3", libelle: "TMS bureau", probabilite: 3, gravite: 2 },
];

export function HseScreen() {
  const [risques, setRisques] = useState<RisqueInput[]>(DEFAULT);
  const [res, setRes] = useState<RisqueEvalue[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const set = (i: number, k: keyof RisqueInput, v: string) =>
    setRisques((l) => l.map((row, j) => (j === i ? { ...row, [k]: k === "libelle" || k === "id_externe" ? v : Number(v) } : row)));
  const add = () => setRisques((l) => [...l, { id_externe: `R${l.length + 1}`, libelle: "", probabilite: 1, gravite: 1 }]);
  const del = (i: number) => setRisques((l) => l.filter((_, j) => j !== i));

  async function run() {
    setErr(null); setRes(null);
    try { setRes((await hseCartographie(risques)).risques); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible."); }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={HardHat} title="HSE — Cartographie des risques" subtitle="Criticité = probabilité × gravité (déterministe), triée." />
      <Card>
        <div className="grid grid-cols-[1fr_90px_90px_32px] gap-2 text-xs font-medium text-muted">
          <span>Risque</span><span>Probabilité (1-5)</span><span>Gravité (1-5)</span><span />
        </div>
        {risques.map((row, i) => (
          <div key={i} className="mt-1 grid grid-cols-[1fr_90px_90px_32px] gap-2">
            <Inp value={row.libelle} onChange={(v) => set(i, "libelle", v)} />
            <Inp value={row.probabilite} type="number" onChange={(v) => set(i, "probabilite", v)} />
            <Inp value={row.gravite} type="number" onChange={(v) => set(i, "gravite", v)} />
            <button onClick={() => del(i)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        <div className="mt-3 flex justify-between">
          <Button variant="ghost" onClick={add}><Plus className="h-4 w-4" /> Risque</Button>
          <Button onClick={run}>Cartographier</Button>
        </div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {res && (
        <Card>
          {res.map((r) => (
            <div key={r.reference} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span className="flex items-center gap-2"><Urg level={r.niveau} /> {r.libelle}</span>
              <span className="text-muted">criticité <b className="text-ink">{r.criticite}</b></span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
