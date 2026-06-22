"use client";

import { useState } from "react";
import { Boxes, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { supplyAnalyze, type StockItemInput, type ReapproSuggestion } from "@/lib/erp";
import { ApiError } from "@/lib/api";

const DEFAULT: StockItemInput[] = [
  { sku: "MED-001", libelle: "Paracétamol", quantite_actuelle: "20", conso_moyenne_jour: "5", delai_appro_jours: 7, stock_securite: "10" },
  { sku: "CON-002", libelle: "Gants", quantite_actuelle: "500", conso_moyenne_jour: "10", delai_appro_jours: 5, stock_securite: "50" },
];

export function SupplyScreen() {
  const [items, setItems] = useState<StockItemInput[]>(DEFAULT);
  const [res, setRes] = useState<{ suggestions: ReapproSuggestion[]; alertes: ReapproSuggestion[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const set = (i: number, k: keyof StockItemInput, v: string) =>
    setItems((l) => l.map((row, j) => (j === i ? { ...row, [k]: k === "delai_appro_jours" ? Number(v) : v } : row)));
  const add = () => setItems((l) => [...l, { sku: "", libelle: "", quantite_actuelle: "0", conso_moyenne_jour: "0", delai_appro_jours: 7, stock_securite: "0" }]);
  const del = (i: number) => setItems((l) => l.filter((_, j) => j !== i));

  async function run() {
    setErr(null); setRes(null);
    try { setRes(await supplyAnalyze(items)); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible."); }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Boxes} title="Supply Chain & Stocks" subtitle="Point de commande, alertes rupture, réapprovisionnement (déterministe)." />
      <Card>
        <div className="grid grid-cols-[90px_1fr_70px_70px_60px_70px_32px] gap-2 text-xs font-medium text-muted">
          <span>SKU</span><span>Article</span><span>Stock</span><span>Conso/j</span><span>Délai</span><span>Sécu</span><span />
        </div>
        {items.map((row, i) => (
          <div key={i} className="mt-1 grid grid-cols-[90px_1fr_70px_70px_60px_70px_32px] gap-2">
            <Inp value={row.sku} onChange={(v) => set(i, "sku", v)} />
            <Inp value={row.libelle} onChange={(v) => set(i, "libelle", v)} />
            <Inp value={row.quantite_actuelle} type="number" onChange={(v) => set(i, "quantite_actuelle", v)} />
            <Inp value={row.conso_moyenne_jour} type="number" onChange={(v) => set(i, "conso_moyenne_jour", v)} />
            <Inp value={row.delai_appro_jours} type="number" onChange={(v) => set(i, "delai_appro_jours", v)} />
            <Inp value={row.stock_securite} type="number" onChange={(v) => set(i, "stock_securite", v)} />
            <button onClick={() => del(i)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        <div className="mt-3 flex justify-between">
          <Button variant="ghost" onClick={add}><Plus className="h-4 w-4" /> Article</Button>
          <Button onClick={run}>Analyser</Button>
        </div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {res && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold">À réapprovisionner ({res.suggestions.length})</h2>
          {res.suggestions.length === 0 && <p className="text-sm text-muted">Aucun réapprovisionnement nécessaire.</p>}
          {res.suggestions.map((s) => (
            <div key={s.sku} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span className="flex items-center gap-2"><Urg level={s.urgence} /> {s.libelle}</span>
              <span className="text-muted">commander <b className="text-ink">{s.quantite_a_commander}</b> · rupture ~{s.jours_avant_rupture ?? "—"} j</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
