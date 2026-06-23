"use client";

import { useCallback, useEffect, useState } from "react";
import { Boxes, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  listStock, createStock, deleteStock, analyzeStock,
  type StockRec, type ReapproSugg,
} from "@/lib/store";

const EMPTY = { sku: "", libelle: "", quantite_actuelle: "0", conso_moyenne_jour: "0", delai_appro_jours: 7, stock_securite: "0" };

export function SupplyScreen() {
  const [items, setItems] = useState<StockRec[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [res, setRes] = useState<{ suggestions: ReapproSugg[]; alertes: ReapproSugg[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const { items: rows } = await listStock();
      setItems(rows);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function add() {
    if (!form.sku) return;
    try {
      await createStock(form);
      setForm({ ...EMPTY });
      setRes(null);
      await refresh();
    } catch { setErr("Ajout impossible (backend/DB)."); }
  }
  async function del(id: string) {
    try { await deleteStock(id); setRes(null); await refresh(); }
    catch { setErr("Suppression impossible."); }
  }
  async function run() {
    setErr(null);
    try { setRes(await analyzeStock()); }
    catch (e) { setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible."); }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Boxes} title="Supply Chain & Stocks" subtitle="Stock persistant + réappro/alertes rupture (déterministe)." />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <Card>
        <h2 className="mb-2 text-sm font-semibold">Ajouter un article</h2>
        <div className="grid grid-cols-[90px_1fr_70px_70px_60px_70px_36px] gap-2">
          <Inp value={form.sku} onChange={(v) => setForm({ ...form, sku: v })} placeholder="SKU" />
          <Inp value={form.libelle} onChange={(v) => setForm({ ...form, libelle: v })} placeholder="Article" />
          <Inp value={form.quantite_actuelle} type="number" onChange={(v) => setForm({ ...form, quantite_actuelle: v })} placeholder="Stock" />
          <Inp value={form.conso_moyenne_jour} type="number" onChange={(v) => setForm({ ...form, conso_moyenne_jour: v })} placeholder="Conso/j" />
          <Inp value={form.delai_appro_jours} type="number" onChange={(v) => setForm({ ...form, delai_appro_jours: Number(v) })} placeholder="Délai" />
          <Inp value={form.stock_securite} type="number" onChange={(v) => setForm({ ...form, stock_securite: v })} placeholder="Sécu" />
          <button onClick={add} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
        </div>
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Stock ({items.length})</h2>
          <Button onClick={run} disabled={items.length === 0}>Analyser</Button>
        </div>
        {items.length === 0 && <p className="text-sm text-muted">Aucun article. Ajoutez-en un.</p>}
        {items.map((it) => (
          <div key={it.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
            <span><b>{it.sku}</b> · {it.libelle}</span>
            <span className="flex items-center gap-3 text-muted">
              stock {it.quantite_actuelle} · conso {it.conso_moyenne_jour}/j
              <button onClick={() => del(it.id)} className="hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
            </span>
          </div>
        ))}
      </Card>

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
