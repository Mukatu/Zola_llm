"use client";

import { useCallback, useEffect, useState } from "react";
import { Boxes, Plus, Trash2, CheckCircle2, ArrowDownToLine, ArrowUpFromLine, Sliders } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { fmt } from "@/lib/data";
import { ApiError } from "@/lib/api";
import {
  listStock,
  createStock,
  deleteStock,
  analyzeStock,
  listStockMoves,
  createStockMove,
  validateStockMove,
  deleteStockMove,
  type StockRec,
  type ReapproSugg,
  type StockMoveRec,
} from "@/lib/store";

const EMPTY = { sku: "", libelle: "", quantite_actuelle: "0", conso_moyenne_jour: "0", delai_appro_jours: 7, stock_securite: "0" };
const TODAY = new Date().toISOString().slice(0, 10);
const TYPE_ICON: Record<string, typeof ArrowDownToLine> = {
  entree: ArrowDownToLine,
  sortie: ArrowUpFromLine,
  ajustement: Sliders,
  transfert: Sliders,
};

export function SupplyScreen() {
  const [items, setItems] = useState<StockRec[]>([]);
  const [moves, setMoves] = useState<StockMoveRec[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [mv, setMv] = useState({ type: "entree", sku: "", quantite: "", cout: "" });
  const [res, setRes] = useState<{ suggestions: ReapproSugg[]; alertes: ReapproSugg[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([listStock(), listStockMoves()]);
      setItems(s.items);
      setMoves(m.moves);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function add() {
    if (!form.sku) return;
    try {
      await createStock(form);
      setForm({ ...EMPTY });
      setRes(null);
      await refresh();
    } catch {
      setErr("Ajout impossible (backend/DB).");
    }
  }
  async function del(id: string) {
    try {
      await deleteStock(id);
      setRes(null);
      await refresh();
    } catch {
      setErr("Suppression impossible.");
    }
  }
  async function run() {
    setErr(null);
    try {
      setRes(await analyzeStock());
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }

  async function addMove() {
    if (!mv.sku || !mv.quantite) return;
    try {
      await createStockMove({
        reference: `MV-${Date.now()}`,
        type: mv.type,
        sku: mv.sku,
        quantite: mv.quantite,
        cout_unitaire_xaf: mv.type === "entree" ? mv.cout || "0" : null,
        date_mouvement: TODAY,
      });
      setMv({ ...mv, quantite: "", cout: "" });
      await refresh();
    } catch {
      setErr("Création du mouvement impossible.");
    }
  }
  async function validate(id: string) {
    try {
      await validateStockMove(id);
      setRes(null);
      await refresh();
    } catch (e) {
      setErr(
        e instanceof ApiError && e.status === 422
          ? "Stock insuffisant pour cette sortie."
          : e instanceof ApiError && e.status === 409
            ? "Mouvement déjà validé."
            : "Validation impossible.",
      );
    }
  }
  async function delMove(id: string) {
    try {
      await deleteStockMove(id);
      await refresh();
    } catch {
      setErr("Suppression impossible (mouvement validé ?).");
    }
  }

  const valeurTotale = items.reduce((s, it) => s + Number(it.valeur_stock_xaf ?? 0), 0);
  const enBrouillon = moves.filter((m) => m.statut === "brouillon").length;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <FlagshipHeader
        icon={Boxes}
        title="Supply Chain & Stocks"
        subtitle="Grand-livre des mouvements valorisé (PMP) + réappro/alertes rupture (déterministe)."
      />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label="Articles" value={String(items.length)} />
        <Kpi label="Valeur du stock" value={fmt(valeurTotale) + " XAF"} />
        <Kpi label="Mouvements" value={String(moves.length)} />
        <Kpi label="À valider" value={String(enBrouillon)} />
      </div>

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
          <h2 className="text-sm font-semibold">Stock valorisé ({items.length})</h2>
          <Button onClick={run} disabled={items.length === 0}>Analyser réappro</Button>
        </div>
        {items.length === 0 && <p className="text-sm text-muted">Aucun article. Ajoutez-en un.</p>}
        {items.map((it) => (
          <div key={it.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
            <span><b>{it.sku}</b> · {it.libelle}</span>
            <span className="flex items-center gap-3 text-muted">
              <span>stock <b className="text-ink">{it.quantite_actuelle}</b></span>
              <span>PMP {fmt(it.pmp_xaf ?? "0")}</span>
              <span>valeur <b className="text-ink">{fmt(it.valeur_stock_xaf ?? "0")}</b> XAF</span>
              <button onClick={() => del(it.id)} className="hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
            </span>
          </div>
        ))}
      </Card>

      {/* Mouvements de stock */}
      <Card>
        <h2 className="mb-2 text-sm font-semibold">Mouvements de stock</h2>
        <div className="mb-3 grid grid-cols-[110px_90px_80px_90px_36px] gap-2">
          <select value={mv.type} onChange={(e) => setMv({ ...mv, type: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {["entree", "sortie", "ajustement", "transfert"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <Inp value={mv.sku} onChange={(v) => setMv({ ...mv, sku: v })} placeholder="SKU" />
          <Inp value={mv.quantite} type="number" onChange={(v) => setMv({ ...mv, quantite: v })} placeholder="Qté" />
          <Inp value={mv.cout} type="number" onChange={(v) => setMv({ ...mv, cout: v })} placeholder="Coût (entrée)" />
          <button onClick={addMove} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
        </div>
        {moves.length === 0 && <p className="text-sm text-muted">Aucun mouvement. Créez-en un (validez pour appliquer au stock).</p>}
        {moves.map((m) => {
          const Icon = TYPE_ICON[m.type] ?? Sliders;
          return (
            <div key={m.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-muted" />
                <b>{m.sku}</b> · {m.type} · {m.quantite}
                {m.statut === "valide" && <span className="text-xs text-muted">({fmt(m.valeur_xaf)} XAF)</span>}
              </span>
              <span className="flex items-center gap-2">
                {m.statut === "valide" ? (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">validé</span>
                ) : (
                  <>
                    <button onClick={() => validate(m.id)} title="Valider → applique au stock" className="text-emerald-600 hover:text-emerald-800"><CheckCircle2 className="h-4 w-4" /></button>
                    <button onClick={() => delMove(m.id)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
                  </>
                )}
              </span>
            </div>
          );
        })}
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

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </Card>
  );
}
